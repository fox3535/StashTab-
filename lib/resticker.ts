// Slice-13 resticker queue — pure helpers.
//
// The accepted authenticated GET /api/v1/admin/inventory/resticker
// contract (services/api/app/routers/admin.py list_resticker_queue)
// returns in-stock items whose recorded sticker price differs from the
// current price rounded up by at least the shop's resticker threshold
// ($2.00 by default). Each row carries id/sku/name/price/sticker_price/
// suggested_sticker only; suggested_sticker is computed by the API. The
// list is sorted by name with NO cap and NO pagination. This screen is
// read-only: it never marks items restickered, prints labels, or changes
// prices.

/** Missing or invalid values render as an honest "—", never a made-up amount. */
export function formatRestickerMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

/** Honest set-size disclosure for the uncapped, unpaginated contract. */
export function restickerSetNotice(count: number): string {
  return `Showing ${count} item${count === 1 ? "" : "s"} returned by the API, sorted by name. This endpoint has no cap and no pagination; it returns the current set in one response.`;
}
