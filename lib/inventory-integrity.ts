// Slice-11 inventory integrity — pure helpers.
//
// Backed only by two accepted authenticated read contracts in
// services/api/app/routers/admin.py:
//   - GET /admin/inventory-truth/status  (list: shop_id, cutover_status,
//     unaccounted) — cutover_status is null when no cutover row exists.
//   - GET /admin/inventory-truth/reconcile (list: shop_id,
//     unaccounted_qty, mismatches) — mismatches map SKU to
//     { event_remaining, snapshot_stock } where snapshot_stock is null
//     when the SKU has no inventory snapshot row.
// Both are pure SELECTs: they never write, repair, backfill, or change
// cutover state. Reconciliation compares inventory snapshots with
// event-derived truth (frozen inventory-truth-v1 DESIGN.md §1 recon).
// This screen never invents a green state: missing, timed-out,
// incomplete, or unavailable data is said plainly.

/**
 * Client-side safety bound for the read-only check. If the two GETs do
 * not complete in time, the request is aborted and an honest timed-out
 * state is shown instead of pretending to be green.
 */
export const INTEGRITY_CHECK_TIMEOUT_MS = 15000;

/**
 * Plain-language cutover status. Cutover-off is stated as a fact — it is
 * never an error and never an approval of anything.
 */
export function describeCutoverStatus(status: string | null | undefined): string {
  if (status === null || status === undefined || status === "") {
    return "Off — no cutover row exists for this shop. Cutover being off is not an error and is not an approval.";
  }
  if (status === "complete") return "Complete";
  return `Status reported by the API: ${status}`;
}

/**
 * Honest outcome text for a completed check. Zero mismatches is reported
 * as what the check returned, not as a permanent guarantee.
 */
export function reconOutcomeText(unaccountedQty: number): string {
  if (unaccountedQty === 0) {
    return "Matched: this check returned zero mismatches. Event-derived truth agreed with the inventory snapshot for every SKU at the time of this check.";
  }
  return `Mismatched: ${unaccountedQty} SKU${unaccountedQty === 1 ? "" : "s"} where event-derived remaining differs from snapshot stock.`;
}

/**
 * Format a reconciliation quantity. Missing values render as an honest
 * "—", never a fabricated number.
 */
export function formatMismatchValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return String(value);
}

/** Honest timed-out disclosure. */
export function timedOutNotice(): string {
  return `The check timed out after ${INTEGRITY_CHECK_TIMEOUT_MS / 1000} seconds. No result is available and nothing was changed.`;
}
