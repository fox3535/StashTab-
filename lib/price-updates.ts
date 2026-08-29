// Slice-10 price update review — pure helpers.
//
// The accepted authenticated GET /api/v1/admin/inventory/updated contract
// (services/api/app/routers/admin.py list_updated_cards) returns the
// shop's inventory records flagged with needs_update == true, meaning the
// API recorded a pending/previous price change for them. It returns
// id/sku/name/old_price/price/shop_listing_price only. The route has NO
// cap and NO pagination: it returns the full current set in one response.
// This screen is read-only: it never approves, dismisses, edits,
// reprices, exports, or mutates anything, and it never infers margin,
// market price, provider price, profit, recommended action, or
// completion status.

/**
 * Above this many returned rows the screen adds a large-result notice.
 * The threshold is a UI hint only — the contract itself is uncapped.
 */
export const PRICE_UPDATES_LARGE_THRESHOLD = 200;

/**
 * Format a price-update money value. Missing optional values render as
 * an honest "—", never a fabricated amount.
 */
export function formatPriceUpdateMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

/**
 * Honest set-size disclosure. Always states the API limitation (no cap,
 * no pagination, no completeness guarantee beyond the current response),
 * and adds a large-result note when the returned set is big.
 */
export function priceUpdateSetNotice(count: number): string {
  const base = `Showing ${count} record${count === 1 ? "" : "s"} returned by the API. This endpoint has no cap and no pagination; it returns the current set in one response.`;
  if (count >= PRICE_UPDATES_LARGE_THRESHOLD) {
    return `${base} This is a large result set; review may take some scrolling.`;
  }
  return base;
}
