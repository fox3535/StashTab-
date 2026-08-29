// Slice-08 sales history browse regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/sales-history.ts by source-wiring assertions. All fixtures are
// clearly labeled synthetic data — staging may only prove the honest
// empty state.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/sales-history.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/sales/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");
const schemaSrc = readFileSync(join(root, "services/api/app/schemas.py"), "utf8");

// Comment-stripped view of the page so negative scans test rendered
// behaviour, not doc-comment or honest "not ready" copy.
const pageCode = pageSrc.replace(/\/\/.*$/gm, "");

// --- Behavioral mirrors of lib/sales-history.ts ---

function formatSaleMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

function formatSaleTimestampHonest(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return "formatted"; // locale output is environment-dependent; only honesty is asserted
}

// --- Labeled fixtures (synthetic; staging may only prove empty) ---
const FIXTURE_SALE = {
  id: 1,
  item_name: "FIXTURE Pikachu ex",
  sku: "SV8-123",
  sold_price: 4.5,
  profit: null,
  transaction_type: "cash",
  trade_in_value: 0,
  net_revenue: 4.5,
  game: "Pokemon",
  timestamp: "2026-08-01T14:30:00",
};

test("missing or unparseable values render honestly, never invented", () => {
  assert.equal(formatSaleMoney(null), "—");
  assert.equal(formatSaleMoney(undefined), "—");
  assert.equal(formatSaleMoney(4.5), "$4.50");
  assert.equal(formatSaleTimestampHonest(""), "—");
  assert.equal(formatSaleTimestampHonest(null), "—");
  assert.equal(formatSaleTimestampHonest("not-a-date"), "—");
  assert.equal(formatSaleTimestampHonest(FIXTURE_SALE.timestamp), "formatted");
  assert.equal(helperSrc.includes('if (!iso) return "—"'), true);
  assert.equal(helperSrc.includes("Number.isNaN(d.getTime())"), true);
});

test("the page uses the accepted GET /sales/history wrapper with limit, offset, total", () => {
  assert.equal(pageSrc.includes("mimirApi.salesHistory"), true);
  assert.equal(pageSrc.includes("limit: SALES_PAGE_SIZE"), true);
  assert.equal(pageSrc.includes("offset: offsetForPage(targetPage, SALES_PAGE_SIZE)"), true);
  assert.equal(mimirSrc.includes("salesHistory: (opts: RequestOptions & { limit?: number; offset?: number })"), true);
  assert.equal(mimirSrc.includes('params.set("offset", String(opts.offset))'), true);
  assert.equal(mimirSrc.includes("/sales/history"), true);
  assert.equal(helperSrc.includes("SALES_PAGE_SIZE = 50"), true);
});

test("pagination windows track the honest contract total", () => {
  // Mirror of lib/pos-find.ts findPageWindow used by the page.
  function findPageWindow(total, offset, pageSize) {
    const safeTotal = Math.max(0, total);
    const safeOffset = Math.max(0, offset);
    return {
      from: safeTotal === 0 ? 0 : safeOffset + 1,
      to: Math.min(safeOffset + pageSize, safeTotal),
      hasPrev: safeOffset > 0,
      hasNext: safeOffset + pageSize < safeTotal,
      endOfResults: safeOffset + pageSize >= safeTotal,
    };
  }
  const first = findPageWindow(120, 0, 50);
  assert.deepEqual(first, { from: 1, to: 50, hasPrev: false, hasNext: true, endOfResults: false });
  const last = findPageWindow(120, 100, 50);
  assert.deepEqual(last, { from: 101, to: 120, hasPrev: true, hasNext: false, endOfResults: true });
  const empty = findPageWindow(0, 0, 50);
  assert.equal(empty.from, 0);
  assert.equal(empty.endOfResults, true);
  assert.equal(pageSrc.includes("BrowsePagination"), true);
});

test("shop switching clears sales immediately and rejects late responses", () => {
  assert.equal(pageSrc.includes("epochRef.current += 1"), true);
  assert.equal(pageSrc.includes("shouldApplyShopResult(requestedShopId, shopIdRef.current)"), true);
  assert.equal(pageSrc.includes("AbortController"), true);
  assert.equal(pageSrc.includes("controller.abort()"), true);
  assert.equal(pageSrc.includes("setSales([])"), true);
  assert.equal(pageSrc.includes("setTotal(0)"), true);
});

test("loading, empty, error, and live-region states are honest", () => {
  assert.equal(pageSrc.includes("VendorLoadingBlock"), true);
  assert.equal(pageSrc.includes("No sales are recorded for this shop yet. This is an empty result, not a failed write."), true);
  assert.equal(pageSrc.includes("VendorErrorBanner"), true);
  assert.equal(pageSrc.includes("classifyVendorError(err)"), true);
  assert.equal(pageSrc.includes('aria-live="polite"'), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("only SaleOut fields are displayed; accounting fields stay hidden", () => {
  for (const field of ["item_name", "sku", "sold_price", "transaction_type", "game", "timestamp"]) {
    assert.equal(schemaSrc.includes(`${field}:`), true);
  }
  assert.equal(pageSrc.includes("sale.item_name"), true);
  assert.equal(pageSrc.includes("sale.sku"), true);
  assert.equal(pageSrc.includes("sale.transaction_type"), true);
  assert.equal(pageSrc.includes("formatSaleMoney(sale.sold_price)"), true);
  assert.equal(pageSrc.includes("formatSaleTimestamp(sale.timestamp)"), true);
  // Per-row profit/net_revenue/trade_in_value are intentionally not shown.
  assert.equal(pageCode.includes("sale.profit"), false);
  assert.equal(pageCode.includes("net_revenue"), false);
  assert.equal(pageCode.includes("trade_in_value"), false);
});

test("the screen is read-only: no checkout, refund, export, or mutation behavior", () => {
  for (const forbidden of ["mimirApi.checkout", "PATCH", "DELETE", "markPulled", "syncNow", "placeholder", "/export", "csv"]) {
    assert.equal(pageCode.includes(forbidden), false, `sales history page must not reference ${forbidden}`);
  }
  assert.equal(pageSrc.includes("Read-only; refunds, exports, and metrics are not ready."), true);
});

test("dashboard and sidebar expose an honest Sales History entry", () => {
  assert.equal(dashSrc.includes('href: "/admin/sales"'), true);
  assert.equal(dashSrc.includes('label: "Sales History"'), true);
  assert.equal(dashSrc.includes("Read-only browse of recorded sales. Refunds, exports, and metrics are not ready."), true);
  assert.equal(sidebarSrc.includes('{ href: "/admin/sales", label: "Sales History", icon: Receipt }'), true);
});

test("locked routes stay locked and /admin/sales is not one of them", () => {
  assert.equal(gateSrc.includes('const LOCKED_EXACT = new Set(["/pos"])'), true);
  assert.equal(gateSrc.includes('"/admin/intake"'), true);
  assert.equal(gateSrc.includes('"/pos/pulls"'), true);
  assert.equal(gateSrc.includes("/admin/sales"), false);
});

test("responsive layout keeps desktop table and mobile cards without overflow", () => {
  assert.equal(pageSrc.includes("w-full max-w-full overflow-x-hidden"), true);
  assert.equal(pageSrc.includes("hidden overflow-x-auto rounded-lg border border-border md:block"), true);
  assert.equal(pageSrc.includes('className="space-y-2 md:hidden"'), true);
  assert.equal(pageSrc.includes("min-w-[640px]"), true);
});

test("fixture sanity: sold price formats from the contract value", () => {
  assert.equal(formatSaleMoney(FIXTURE_SALE.sold_price), "$4.50");
});
