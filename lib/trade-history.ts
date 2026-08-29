// Slice-09 recent trade history — pure helpers.
//
// The accepted authenticated GET /api/v1/reports/trade-history contract
// (services/api/app/routers/reports.py trade_history) returns genuinely
// trade-typed sale records (transaction_type == "trade") scoped to the
// verified membership's shop, newest-first, with a FIXED cap of 200 rows.
// It has no pagination, no offset, and no total. This screen is
// read-only: it never creates, refunds, exports, or mutates anything,
// and it never invents totals, profit, margin, customer, payment, tax,
// or inventory data.

/** The contract's fixed cap; the screen shows at most this many rows. */
export const TRADE_HISTORY_CAP = 200;

/**
 * Format a trade timestamp for display. The contract returns an ISO
 * datetime or null; anything missing or unparseable renders as an honest
 * "—", never a fabricated date.
 */
export function formatTradeTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const date = d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const time = d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${date}, ${time}`;
}

/**
 * Format a trade money value. Missing optional values render as "—".
 */
export function formatTradeMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

/**
 * Honest capped-results notice. Only shown when the contract returned
 * exactly its fixed cap, because that is the only observable signal that
 * older trades may exist beyond the window.
 */
export function cappedTradeNotice(count: number): string {
  if (count >= TRADE_HISTORY_CAP) {
    return `Showing the newest ${TRADE_HISTORY_CAP} trades. Older trades exist beyond this window; complete history is not available here.`;
  }
  return `Showing the newest ${count} trade${count === 1 ? "" : "s"}. This endpoint returns up to ${TRADE_HISTORY_CAP} records and does not paginate.`;
}
