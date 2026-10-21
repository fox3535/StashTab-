// Slice-14 dashboard metrics — pure helpers.
//
// The accepted authenticated GET /api/v1/admin/dashboard contract
// (services/api/app/routers/admin.py dashboard_kpis) returns seven
// shop-scoped figures. Owner decisions D1–D4 (PLAN-SLICE-14) allow this
// dashboard to show exactly three of them:
// - inventory_count: inventory rows (SKUs) with stock > 0, not units;
// - inventory_value: sum of current sell price x stock, not cost;
// - paperweight_units: the same total as the Paperweight Report.
// Sales money, staging, and Shopify sync figures are deliberately not
// read. Missing or non-numeric values render as "—", never as 0.

const countFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const moneyFormat = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Whole-number count with thousands separators, or "—". */
export function formatMetricCount(value: unknown): string {
  return isFiniteNumber(value) ? countFormat.format(value) : "—";
}

/** US-dollar amount with cents and thousands separators, or "—". */
export function formatMetricMoney(value: unknown): string {
  return isFiniteNumber(value) ? moneyFormat.format(value) : "—";
}

/** True only for a real positive number (drives the ember warning tone). */
export function isPositiveMetric(value: unknown): boolean {
  return isFiniteNumber(value) && value > 0;
}
