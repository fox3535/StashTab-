// Slice-08 sales history browse — pure helpers.
//
// The accepted authenticated GET /api/v1/sales/history contract
// (services/api/app/routers/sales.py sales_history, SalesHistoryResponse)
// returns shop-scoped sale records ordered newest-first with an honest
// record-count total plus limit/offset pagination. This screen is
// read-only: it never creates, refunds, cancels, exports, or mutates
// anything, and it never computes revenue metrics, trends, or aggregates
// that the contract does not return.

export const SALES_PAGE_SIZE = 50;

/**
 * Format a SaleOut timestamp for display. The contract returns an ISO
 * datetime; anything missing or unparseable renders as an honest "—",
 * never a fabricated date.
 */
export function formatSaleTimestamp(iso: string | null | undefined): string {
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
 * Format a SaleOut money value. Missing optional values render as "—".
 */
export function formatSaleMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}
