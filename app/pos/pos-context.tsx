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
import {
  itemSellPrice,
  mimirApi,
  type InventoryItem,
  type PlaceholderTrade,
} from "@/lib/mimir-api";

export type CartLine = InventoryItem & { cartQty: number };

type PosContextValue = {
  shopId: string;
  shopReady: boolean;
  clerkUserId?: string;
  apiOpts: { shopId: string; clerkUserId?: string };
  cart: CartLine[];
  addToCart: (item: InventoryItem) => void;
  removeFromCart: (sku: string) => void;
  updateCartQty: (sku: string, qty: number) => void;
  clearCart: () => void;
  cartTotal: number;
  placeholderTrades: PlaceholderTrade[];
  refreshPlaceholderTrades: () => Promise<void>;
  activeShowId: string | null;
  setActiveShowId: (id: string | null) => void;
};

const PosContext = createContext<PosContextValue | null>(null);

export function PosProvider({ children }: { children: ReactNode }) {
  const devShopId = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";
  const { userId, getToken } = useAuth();
  const [shopId, setShopId] = useState("");
  const [shopReady, setShopReady] = useState(false);
  const [authToken, setAuthToken] = useState<string | undefined>();
  const [cart, setCart] = useState<CartLine[]>([]);
  const [placeholderTrades, setPlaceholderTrades] = useState<PlaceholderTrade[]>([]);
  const [activeShowId, setActiveShowId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadToken() {
      if (!getToken) return;
      const token = await getToken();
      if (!cancelled) setAuthToken(token ?? undefined);
    }
    loadToken();
    return () => {
      cancelled = true;
    };
  }, [getToken, userId]);

  useEffect(() => {
    let cancelled = false;

    async function resolveShop() {
      if (userId) {
        try {
          const shop = await mimirApi.getMyShop(userId);
          if (!cancelled) setShopId(shop.id);
        } catch {
          if (!cancelled && devShopId) setShopId(devShopId);
        }
      } else if (devShopId) {
        setShopId(devShopId);
      }
      if (!cancelled) setShopReady(true);
    }

    resolveShop();
    return () => {
      cancelled = true;
    };
  }, [userId, devShopId]);

  const apiOpts = useMemo(
    () => ({
      shopId,
      clerkUserId: userId ?? undefined,
      authToken,
    }),
    [shopId, userId, authToken]
  );

  const cartTotal = useMemo(
    () => cart.reduce((sum, line) => sum + itemSellPrice(line) * line.cartQty, 0),
    [cart]
  );

  const addToCart = useCallback((item: InventoryItem) => {
    setCart((prev) => {
      const existing = prev.find((l) => l.sku === item.sku);
      if (existing) {
        if (existing.cartQty >= item.stock) return prev;
        return prev.map((l) =>
          l.sku === item.sku ? { ...l, cartQty: l.cartQty + 1 } : l
        );
      }
      return [...prev, { ...item, cartQty: 1 }];
    });
  }, []);

  const removeFromCart = useCallback((sku: string) => {
    setCart((prev) => prev.filter((l) => l.sku !== sku));
  }, []);

  const updateCartQty = useCallback((sku: string, qty: number) => {
    setCart((prev) =>
      prev
        .map((l) => (l.sku === sku ? { ...l, cartQty: qty } : l))
        .filter((l) => l.cartQty > 0)
    );
  }, []);

  const clearCart = useCallback(() => setCart([]), []);

  const refreshPlaceholderTrades = useCallback(async () => {
    if (!shopId) return;
    const trades = await mimirApi.getPlaceholderTrades(apiOpts);
    setPlaceholderTrades(trades);
  }, [shopId, apiOpts]);

  if (!shopReady) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center gap-2 bg-obsidian font-mono text-sm text-steel">
        <span className="size-1.5 animate-blink rounded-full bg-neon" />
        Loading shop…
      </div>
    );
  }

  return (
    <PosContext.Provider
      value={{
        shopId,
        shopReady,
        clerkUserId: userId ?? undefined,
        apiOpts,
        cart,
        addToCart,
        removeFromCart,
        updateCartQty,
        clearCart,
        cartTotal,
        placeholderTrades,
        refreshPlaceholderTrades,
        activeShowId,
        setActiveShowId,
      }}
    >
      {children}
    </PosContext.Provider>
  );
}

export function usePos() {
  const ctx = useContext(PosContext);
  if (!ctx) throw new Error("usePos must be used within PosProvider");
  return ctx;
}
