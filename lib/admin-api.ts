const API_BASE = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8001";
const API_PREFIX = "/api/v1";
const DEFAULT_SHOP_ID = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";

export type AdminAuth = {
  shopId?: string;
  authToken?: string | null;
  clerkUserId?: string | null;
};

async function adminFetch(
  path: string,
  init?: RequestInit,
  auth: AdminAuth = {}
) {
  const shopId = auth.shopId || DEFAULT_SHOP_ID;
  const headers: Record<string, string> = {
    "X-Shop-Id": shopId,
    ...(init?.headers as Record<string, string>),
  };
  if (auth.authToken) {
    headers.Authorization = `Bearer ${auth.authToken}`;
  } else if (auth.clerkUserId) {
    headers["X-Clerk-User-Id"] = auth.clerkUserId;
  }
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(`${API_BASE}${API_PREFIX}${path}`, { ...init, headers });
}

export type CardLookupResult = {
  clean_name: string;
  high_res_image: string | null;
  market_price: number | null;
  official_set_name: string;
  official_set_number: string;
};

export type StagingItem = {
  id: number;
  sku: string;
  name: string;
  market_price: number;
  suggested_price: number;
  image_url: string | null;
  quantity: number;
  set_name: string | null;
  sequence_number: string | null;
};

export type ShopSettings = {
  buy_percentage: number;
  trade_percentage: number;
  rounding_strategy: string;
  markup_type?: string;
  markup_value?: number;
  rounding_rule?: string;
  resticker_threshold?: number;
  price_fluctuation_threshold?: number;
  paperweight_days?: number;
  pokemon_icon_url?: string;
  one_piece_icon_url?: string;
  auto_sync_enabled?: boolean;
};

export type ShippingRule = {
  id: number;
  min_price: number;
  max_price: number;
  additional_cost: number;
  card_type: string;
};

export type ShopifyCredentialsStatus = {
  configured: boolean;
  store_url: string;
  api_key_masked: string | null;
};

export type ShopMember = {
  id: string;
  shop_id: string;
  clerk_user_id: string;
  role: string;
};

export type InventoryRow = {
  id: number;
  sku: string;
  name: string;
  stock: number;
  price: number;
  sticker_price?: number | null;
  cost: number;
  game: string;
  sync_status: string;
  image_url?: string | null;
  set_name?: string | null;
};

export const adminApi = {
  lookupCard: async (
    payload: { set_name: string; sequence_number: string; card_name?: string },
    auth?: AdminAuth
  ) => {
    const res = await adminFetch("/admin/intake/lookup", {
      method: "POST",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<CardLookupResult>;
  },

  addToStaging: async (
    payload: {
      name: string;
      set_name?: string;
      sequence_number?: string;
      market_price: number;
      image_url?: string;
      quantity?: number;
      card_type?: string;
      game?: string;
    },
    auth?: AdminAuth
  ) => {
    const res = await adminFetch("/admin/intake/staging", {
      method: "POST",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  listStaging: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/staging", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    return data.items as StagingItem[];
  },

  commitStaging: async (id: number, auth?: AdminAuth) => {
    const res = await adminFetch(`/admin/staging/${id}/commit`, { method: "POST" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  commitAllStaging: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/staging/commit-all", { method: "POST" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getSettings: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/settings", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<ShopSettings>;
  },

  updateSettings: async (payload: Partial<ShopSettings>, auth?: AdminAuth) => {
    const res = await adminFetch("/admin/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getShopifyCredentials: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/shopify/credentials", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<ShopifyCredentialsStatus>;
  },

  saveShopifyCredentials: async (
    payload: { store_url: string; api_key: string },
    auth?: AdminAuth
  ) => {
    const res = await adminFetch("/admin/shopify/credentials", {
      method: "PUT",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  testShopifyConnection: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/shopify/test", { method: "POST" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ success: boolean; message: string }>;
  },

  verifyShopify: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/shopify/verify", { method: "POST" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ success: boolean; message: string }>;
  },

  listMembers: async (auth?: AdminAuth) => {
    const shopId = auth?.shopId || DEFAULT_SHOP_ID;
    if (!shopId) return [];
    const res = await adminFetch(`/shops/${shopId}/members`, undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<ShopMember[]>;
  },

  inviteMember: async (
    payload: { clerk_user_id: string; role?: string },
    auth?: AdminAuth
  ) => {
    const shopId = auth?.shopId || DEFAULT_SHOP_ID;
    if (!shopId) throw new Error("Missing shop ID");
    const res = await adminFetch(`/shops/${shopId}/members`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<ShopMember>;
  },

  listInventory: async (
    params: { q?: string; limit?: number; offset?: number },
    auth?: AdminAuth
  ) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.offset) qs.set("offset", String(params.offset));
    const res = await adminFetch(`/admin/inventory?${qs}`, undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ items: InventoryRow[]; total: number }>;
  },

  updateInventoryItem: async (
    id: number,
    payload: { stock?: number; price?: number; sticker_price?: number; sync_status?: string },
    auth?: AdminAuth
  ) => {
    const res = await adminFetch(`/admin/inventory/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  importCsv: async (file: File, auth?: AdminAuth) => {
    const form = new FormData();
    form.append("file", file);
    const res = await adminFetch("/admin/import", { method: "POST", body: form }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{
      success: boolean;
      imported: number;
      updated: number;
      errors: number;
      total_rows: number;
    }>;
  },

  listPendingTrades: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/pending-trades", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    return data.trades as {
      id: number;
      total_market_value: number;
      total_cash_paid: number;
      status: string;
    }[];
  },

  applyTradesToStaging: async (tradeIds: number[], auth?: AdminAuth) => {
    const res = await adminFetch("/admin/staging/apply-trades", {
      method: "POST",
      body: JSON.stringify({ trade_ids: tradeIds }),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ success: boolean; message: string }>;
  },

  listRestickerQueue: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/inventory/resticker", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    return data.items as {
      id: number;
      sku: string;
      name: string;
      price: number;
      sticker_price: number;
      suggested_sticker: number;
    }[];
  },

  markRestickered: async (id: number, auth?: AdminAuth) => {
    const res = await adminFetch(`/admin/inventory/${id}/resticker`, { method: "POST" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  markAllRestickered: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/inventory/resticker-all", { method: "POST" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ success: boolean; marked: number }>;
  },

  listPaperweight: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/inventory/paperweight", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{
      units: number;
      items: Array<{
        id: number;
        sku: string;
        name: string;
        stock: number;
        price: number;
        date_added: string | null;
      }>;
    }>;
  },

  generateLabel: async (
    itemId: number,
    format: string = "QR",
    auth?: AdminAuth
  ) => {
    const res = await adminFetch(`/admin/inventory/${itemId}/label`, {
      method: "POST",
      body: JSON.stringify({ format }),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ success: boolean; sku: string; image_url: string }>;
  },

  listShippingRules: async (auth?: AdminAuth) => {
    const res = await adminFetch("/admin/shipping-rules", undefined, auth);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    return data.rules as ShippingRule[];
  },

  createShippingRule: async (
    payload: Omit<ShippingRule, "id">,
    auth?: AdminAuth
  ) => {
    const res = await adminFetch("/admin/shipping-rules", {
      method: "POST",
      body: JSON.stringify(payload),
    }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  deleteShippingRule: async (id: number, auth?: AdminAuth) => {
    const res = await adminFetch(`/admin/shipping-rules/${id}`, { method: "DELETE" }, auth);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
