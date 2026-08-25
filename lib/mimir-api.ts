import {
  buildProtectedApiHeaders,
  SessionExpiredError,
  type ProtectedApiAuth,
} from "@/lib/protected-api-headers";

const API_BASE = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8001";
const API_PREFIX = "/api/v1";

export type InventoryItem = {
  id: number;
  sku: string;
  name: string;
  set_name?: string | null;
  sequence_number?: string | null;
  cost: number;
  price: number;
  sticker_price?: number | null;
  shop_listing_price?: number | null;
  stock: number;
  condition?: string | null;
  variant?: string | null;
  card_type?: string | null;
  game: string;
  sync_status: string;
  image_url?: string | null;
};

export type SaleRecord = {
  id: number;
  item_name: string | null;
  sku: string | null;
  sold_price: number | null;
  profit: number | null;
  transaction_type: string | null;
  trade_in_value: number;
  net_revenue: number;
  game: string;
  timestamp: string;
};

export type PlaceholderTrade = {
  id: number;
  total_market_value: number;
  total_cash_paid: number;
  status: string;
};

export type PullQueueItem = {
  id: number;
  sku: string;
  order_id: string | null;
  status: string;
  timestamp: string;
};

export type OnlineNotification = {
  id: number;
  type: string;
  card_name: string;
  sku: string;
  order_id: string | null;
  timestamp: string | null;
};

export type ShopRecord = {
  id: string;
  name: string;
  slug: string;
};

export type ShowSession = {
  id: string;
  name: string;
  started_at: string;
  ended_at: string | null;
  status: string;
};

type RequestOptions = {
  shopId?: string;
  authToken?: string;
};

type MimirAuthProvider = () => Promise<ProtectedApiAuth>;
let mimirAuthProvider: MimirAuthProvider | null = null;

export function setMimirAuthProvider(provider: MimirAuthProvider | null) {
  mimirAuthProvider = provider;
}

async function resolveMimirAuth(options: RequestOptions): Promise<ProtectedApiAuth> {
  if (options.authToken && options.authToken.trim()) {
    return { authToken: options.authToken, shopId: options.shopId };
  }
  if (mimirAuthProvider) {
    const provided = await mimirAuthProvider();
    return {
      authToken: provided.authToken,
      shopId: options.shopId || provided.shopId,
    };
  }
  throw new SessionExpiredError();
}

async function mimirFetch<T>(
  path: string,
  options: RequestOptions,
  init?: RequestInit
): Promise<T> {
  const resolved = await resolveMimirAuth(options);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...buildProtectedApiHeaders(resolved),
  };

  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string>) },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `API error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export function getApiBase(): string {
  return API_BASE;
}

export function itemSellPrice(item: InventoryItem): number {
  return item.sticker_price && item.sticker_price > 0
    ? item.sticker_price
    : item.price;
}

const PLACEHOLDER_IMAGE =
  "https://placehold.co/100x140/1e293b/94a3b8?text=No+Image";

/** Matches partner Mimir get_item_image_url() fallback chain. */
export function getItemImageUrl(item: InventoryItem): string {
  if (item.image_url?.startsWith("http")) return item.image_url;
  if (item.image_url) {
    const url = item.image_url.replace(/\\/g, "/");
    if (url.startsWith("/")) return `${getApiBase()}${url}`;
    return url;
  }
  return PLACEHOLDER_IMAGE;
}

export const mimirApi = {
  health: () =>
    fetch(`${API_BASE}${API_PREFIX}/health`).then((r) => r.json()),

  createShop: (name: string, slug: string, opts: RequestOptions) =>
    mimirFetch<ShopRecord>("/shops", opts, {
      method: "POST",
      body: JSON.stringify({ name, slug }),
    }),

  getMyShop: (opts: RequestOptions = {}) =>
    mimirFetch<ShopRecord>("/shops/me", opts),

  searchInventory: (
    q: string,
    opts: RequestOptions & { game?: string; limit?: number }
  ) => {
    const params = new URLSearchParams({ q });
    if (opts.game) params.set("game", opts.game);
    if (opts.limit) params.set("limit", String(opts.limit));
    return mimirFetch<{ items: InventoryItem[]; total: number }>(
      `/inventory/search?${params}`,
      opts
    );
  },

  getInventoryBySku: (sku: string, opts: RequestOptions) =>
    mimirFetch<InventoryItem>(`/inventory/${encodeURIComponent(sku)}`, opts),

  checkout: (
    payload: {
      lines: { sku: string; quantity: number }[];
      payment_method: "cash" | "trade" | "card";
      final_sale_price?: number;
      amount_tendered?: number;
      store_cash?: number;
      customer_cash?: number;
      placeholder_cost?: number;
      clear_placeholder_trades?: boolean;
      show_session_id?: string;
    },
    opts: RequestOptions
  ) =>
    mimirFetch<{
      success: boolean;
      total: number;
      change_due: number;
      net_due: number;
      sale_ids: number[];
    }>("/sales/checkout", opts, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  salesHistory: (opts: RequestOptions & { limit?: number }) => {
    const params = new URLSearchParams();
    if (opts.limit) params.set("limit", String(opts.limit));
    return mimirFetch<{ sales: SaleRecord[]; total: number }>(
      `/sales/history?${params}`,
      opts
    );
  },

  addPlaceholderTrade: (
    payload: { market_value: number; cash_paid: number },
    opts: RequestOptions
  ) =>
    mimirFetch<PlaceholderTrade>("/sales/placeholder-trade", opts, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPlaceholderTrades: (opts: RequestOptions) =>
    mimirFetch<PlaceholderTrade[]>("/sales/placeholder-trades", opts),

  listPulls: (opts: RequestOptions) =>
    mimirFetch<PullQueueItem[]>("/inventory/pulls", opts),

  markPulled: (pullId: number, opts: RequestOptions) =>
    mimirFetch<{ success: boolean }>(
      `/inventory/pulls/${pullId}/mark-pulled`,
      opts,
      { method: "POST" }
    ),

  syncStatus: (opts: RequestOptions) =>
    mimirFetch<{ pending_count: number; last_sync_at: string | null }>(
      "/sync/status",
      opts
    ),

  syncNow: (opts: RequestOptions) =>
    mimirFetch<{ status: string }>("/sync/now", opts, { method: "POST" }),

  pullOrders: (opts: RequestOptions) =>
    mimirFetch<{ new_pulls: number; notifications: OnlineNotification[]; message: string }>(
      "/sync/pull-orders",
      opts,
      { method: "POST" }
    ),

  syncNotifications: (opts: RequestOptions) =>
    mimirFetch<{ notifications: OnlineNotification[] }>(
      "/sync/notifications",
      opts
    ),

  listShowSessions: (opts: RequestOptions) =>
    mimirFetch<ShowSession[]>("/shows", opts),

  startShow: (name: string, opts: RequestOptions) =>
    mimirFetch<ShowSession>("/shows/start", opts, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  endShow: (showId: string, opts: RequestOptions) =>
    mimirFetch<ShowSession>(`/shows/${showId}/end`, opts, { method: "POST" }),

  showPnL: (showId: string, opts: RequestOptions) =>
    mimirFetch<{
      show_id: string;
      name: string;
      total_revenue: number;
      total_profit: number;
      sale_count: number;
    }>(`/shows/${showId}/pnl`, opts),

  captureShowPrices: (opts: RequestOptions, name?: string) =>
    mimirFetch<{ success: boolean; message: string; item_count?: number }>(
      "/shows/capture-prices",
      opts,
      { method: "POST", body: JSON.stringify({ name }) }
    ),

  verifyShopify: (opts: RequestOptions) =>
    mimirFetch<{ success: boolean; message: string }>("/sync/verify", opts, {
      method: "POST",
    }),
};
