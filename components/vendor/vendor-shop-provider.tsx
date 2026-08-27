"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@clerk/nextjs";
import { mimirApi, setMimirAuthProvider } from "@/lib/mimir-api";
import { setAdminAuthProvider } from "@/lib/admin-api";
import { SessionExpiredError } from "@/lib/protected-api-headers";
import {
  classifyVendorError,
  type VendorErrorKind,
} from "@/lib/vendor-api-error";
import {
  clearShopPreference,
  parseMembershipsPayload,
  readShopPreference,
  resolveShopSelection,
  writeShopPreference,
  type MembershipShop,
} from "@/lib/shop-session";

type ShopPhase = "loading" | "choose" | "ready" | "empty" | "session" | "error";

type VendorShopContextValue = {
  shops: MembershipShop[];
  selectedShop: MembershipShop | null;
  phase: ShopPhase;
  message: string;
  selectShop: (shopId: string) => void;
  reload: () => Promise<void>;
  reportApiError: (err: unknown) => VendorErrorKind;
  clearLocalSession: () => void;
};

const VendorShopContext = createContext<VendorShopContextValue | null>(null);

export function VendorShopProvider({ children }: { children: ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [shops, setShops] = useState<MembershipShop[]>([]);
  const [selectedShop, setSelectedShop] = useState<MembershipShop | null>(null);
  const [phase, setPhase] = useState<ShopPhase>("loading");
  const [message, setMessage] = useState("");

  const clearLocalSession = useCallback(() => {
    clearShopPreference();
    setShops([]);
    setSelectedShop(null);
    setMessage("");
    setPhase("session");
  }, []);

  const selectShop = useCallback(
    (shopId: string) => {
      const shop = shops.find((row) => row.id === shopId);
      if (!shop) return;
      writeShopPreference(shop.id);
      setSelectedShop(shop);
      setPhase("ready");
      setMessage("");
    },
    [shops]
  );

  const reportApiError = useCallback(
    (err: unknown): VendorErrorKind => {
      const classified = classifyVendorError(err);
      if (classified.kind === "session_expired") {
        clearShopPreference();
        setSelectedShop(null);
        setPhase("session");
        setMessage(classified.message);
      } else if (classified.kind === "forbidden") {
        clearShopPreference();
        setSelectedShop(null);
        setPhase(shops.length > 1 ? "choose" : "empty");
        setMessage(classified.message);
      } else if (classified.kind === "conflict") {
        clearShopPreference();
        setSelectedShop(null);
        setPhase("choose");
        setMessage(classified.message);
      }
      return classified.kind;
    },
    [shops.length]
  );

  const reload = useCallback(async () => {
    setPhase("loading");
    setMessage("");
    try {
      const token = await getToken();
      if (!token) {
        clearShopPreference();
        setPhase("session");
        setMessage("Session expired. Sign in again.");
        return;
      }
      const payload = await mimirApi.listMyMemberships({ authToken: token });
      const nextShops = parseMembershipsPayload(payload);
      setShops(nextShops);
      const decision = resolveShopSelection(nextShops, readShopPreference());
      if (decision.kind === "empty") {
        clearShopPreference();
        setSelectedShop(null);
        setPhase("empty");
        setMessage("No shop access.");
        return;
      }
      if (decision.kind === "auto") {
        writeShopPreference(decision.shop.id);
        setSelectedShop(decision.shop);
        setPhase("ready");
        return;
      }
      if (decision.kind === "preferred") {
        setSelectedShop(decision.shop);
        setPhase("ready");
        return;
      }
      if (decision.discardedStale) clearShopPreference();
      setSelectedShop(null);
      setPhase("choose");
      setMessage(
        decision.discardedStale
          ? "Saved shop is no longer authorized. Choose a shop you can access."
          : "Choose a shop."
      );
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        clearShopPreference();
        setPhase("session");
        setMessage("Session expired. Sign in again.");
        return;
      }
      const classified = classifyVendorError(err);
      if (classified.kind === "session_expired") {
        clearShopPreference();
        setPhase("session");
        setMessage(classified.message);
        return;
      }
      setPhase("error");
      setMessage(classified.message);
    }
  }, [getToken]);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setPhase("session");
      setMessage("Sign in required.");
      return;
    }
    void reload();
  }, [isLoaded, isSignedIn, reload]);

  useEffect(() => {
    const provide = async () => {
      const token = await getToken();
      if (!token) throw new SessionExpiredError();
      return { authToken: token, shopId: selectedShop?.id };
    };
    setMimirAuthProvider(provide);
    setAdminAuthProvider(provide);
    return () => {
      setMimirAuthProvider(null);
      setAdminAuthProvider(null);
    };
  }, [getToken, selectedShop?.id]);

  const value = useMemo(
    () => ({
      shops,
      selectedShop,
      phase,
      message,
      selectShop,
      reload,
      reportApiError,
      clearLocalSession,
    }),
    [shops, selectedShop, phase, message, selectShop, reload, reportApiError, clearLocalSession]
  );

  return (
    <VendorShopContext.Provider value={value}>{children}</VendorShopContext.Provider>
  );
}

export function useVendorShop() {
  const ctx = useContext(VendorShopContext);
  if (!ctx) throw new Error("useVendorShop must be used inside VendorShopProvider");
  return ctx;
}
