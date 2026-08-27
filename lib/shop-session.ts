export const SHOP_PREFERENCE_KEY = "stashtab.shopPreference";

export type MembershipShop = {
  id: string;
  name: string;
  role: string;
};

export type ShopSelection =
  | { kind: "empty" }
  | { kind: "auto"; shop: MembershipShop; discardedStale: boolean }
  | { kind: "preferred"; shop: MembershipShop }
  | { kind: "choose"; shops: MembershipShop[]; discardedStale: boolean };

const ALLOWED_ROLES = new Set(["owner", "staff"]);

export function parseMembershipsPayload(payload: unknown): MembershipShop[] {
  if (!payload || typeof payload !== "object") {
    throw new Error("Invalid memberships payload");
  }
  const shops = (payload as { shops?: unknown }).shops;
  if (!Array.isArray(shops)) {
    throw new Error("Invalid memberships payload");
  }
  const rows: MembershipShop[] = [];
  for (const row of shops) {
    if (!row || typeof row !== "object") {
      throw new Error("Invalid memberships payload");
    }
    const rec = row as { id?: unknown; name?: unknown; role?: unknown };
    if (typeof rec.id !== "string" || !rec.id.trim()) {
      throw new Error("Invalid memberships payload");
    }
    if (typeof rec.name !== "string") {
      throw new Error("Invalid memberships payload");
    }
    if (typeof rec.role !== "string" || !ALLOWED_ROLES.has(rec.role)) {
      throw new Error("Invalid memberships payload");
    }
    rows.push({ id: rec.id, name: rec.name, role: rec.role });
  }
  return rows;
}

export function normalizeStoredShopId(storedId: string | null | undefined): string | null {
  const stored = (storedId ?? "").trim();
  if (!stored) return null;
  if (stored.length > 80 || /[\s<>]/.test(stored)) return null;
  return stored;
}

export function shouldApplyShopResult(requestShopId: string, currentShopId: string | null | undefined): boolean {
  return Boolean(currentShopId) && requestShopId === currentShopId;
}

export function resolveShopSelection(
  shops: MembershipShop[],
  storedId: string | null | undefined
): ShopSelection {
  if (shops.length === 0) return { kind: "empty" };
  const stored = normalizeStoredShopId(storedId);
  const hadPref = Boolean((storedId ?? "").trim());
  const match = stored ? shops.find((shop) => shop.id === stored) : undefined;
  const discardedStale = hadPref && !match;
  if (shops.length === 1) {
    return {
      kind: "auto",
      shop: shops[0],
      discardedStale,
    };
  }
  if (match) return { kind: "preferred", shop: match };
  return {
    kind: "choose",
    shops,
    discardedStale,
  };
}

export function readShopPreference(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(SHOP_PREFERENCE_KEY);
  } catch {
    return null;
  }
}

export function writeShopPreference(shopId: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SHOP_PREFERENCE_KEY, shopId);
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearShopPreference() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(SHOP_PREFERENCE_KEY);
  } catch {
    /* ignore */
  }
}
