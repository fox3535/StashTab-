// Slice-12 paperweight report — pure helpers.
//
// The accepted authenticated GET /api/v1/admin/inventory/paperweight
// contract (services/api/app/routers/admin.py paperweight_queue) returns:
// - units: total stock across every in-stock item added before the shop's
//   paperweight cutoff (uncapped);
// - items: at most the 100 oldest of those items, oldest first, each with
//   id/sku/name/stock/price/date_added only.
// The cutoff is the shop's paperweight_days setting (60 by default); the
// response does not include the configured value. This screen is
// read-only: it never discounts, reprices, relists, or mutates anything.

/** The API returns at most this many items (list_paperweight_items limit). */
export const PAPERWEIGHT_LIST_CAP = 100;

/** Missing or invalid values render as an honest "—", never a made-up amount. */
export function formatPaperweightMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

/**
 * Format date_added as a UTC calendar date (YYYY-MM-DD). Missing or
 * unparseable values render as "—".
 */
export function formatPaperweightDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toISOString().slice(0, 10);
}

/**
 * Honest list disclosure. States how many items are shown, that the unit
 * total covers every qualifying item, and when the list may be cut off by
 * the API cap.
 */
export function paperweightListNotice(itemCount: number, units: number): string {
  const shown = `Showing ${itemCount} item${itemCount === 1 ? "" : "s"}, oldest first. The ${units} unit total counts every qualifying item.`;
  if (itemCount >= PAPERWEIGHT_LIST_CAP) {
    return `${shown} The API returns at most the ${PAPERWEIGHT_LIST_CAP} oldest items, so more may exist than are listed here.`;
  }
  return shown;
}
