// Slice-15 read-only staging queue — pure helpers.
//
// The accepted authenticated GET /api/v1/admin/staging contract
// (services/api/app/routers/admin.py list_staging) returns at most the 100
// newest staged items, newest first, with no total and no pagination. Each
// row carries id/sku/name/set_name/sequence_number/market_price/
// suggested_price/image_url/quantity plus the slice-15 read-only fields
// condition/variant/card_type/needs_review. cost_basis is never returned.
// Committing staging is the inventory-truth receive path (held F2 work), so
// this screen never commits, edits, removes, refetches, or applies trades.

/** The API returns at most this many staged items (list_staging limit). */
export const STAGING_LIST_CAP = 100;

/** Missing or invalid values render as an honest "—", never a made-up amount. */
export function formatStagingMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

/** "Set · #number", whichever parts exist; "—" when neither does. */
export function stagingSetLine(setName: string | null | undefined, sequence: string | null | undefined): string {
  const parts = [setName?.trim(), sequence?.trim() ? `#${sequence.trim()}` : ""].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

/** "Condition · variant", whichever parts exist; "—" when neither does. */
export function stagingConditionLine(condition: string | null | undefined, variant: string | null | undefined): string {
  const parts = [condition?.trim(), variant?.trim()].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

/** Honest list disclosure, adding the cap warning when it may apply. */
export function stagingListNotice(count: number): string {
  const shown = `Showing ${count} staged item${count === 1 ? "" : "s"}, newest first.`;
  if (count >= STAGING_LIST_CAP) {
    return `${shown} The API returns at most the ${STAGING_LIST_CAP} newest, so more may be staged than are listed here.`;
  }
  return shown;
}
