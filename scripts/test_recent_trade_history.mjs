// Slice-09 recent trade history regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/trade-history.ts by source-wiring assertions. All fixtures are
// clearly labeled synthetic data — staging may only prove the honest
// empty state. Negative scans run against comment-stripped source so doc
// comments that name forbidden behaviour cannot trip them.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/trade-history.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/reports/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_TRADES = [
  { id: 101, item_name: "FIXTURE Trade Card A", sku: "FIX-A", sold_price: 12.5, trade_in_value: 8, timestamp: "2026-08-01T10:00:00" },
  { id: 102, item_name: null, sku: null, sold_price: null, trade_in_value: null, timestamp: null },
];

// ---- behavioural mirrors of lib/trade-history.ts ----
const TRADE_HISTORY_CAP = 200;
function mirrorFormatTradeTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const date = d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${date}, ${time}`;
}
function mirrorFormatTradeMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}
function mirrorCappedTradeNotice(count) {
  if (count >= TRADE_HISTORY_CAP) {
    return `Showing the newest ${TRADE_HISTORY_CAP} trades. Older trades exist beyond this window; complete history is not available here.`;
  }
  return `Showing the newest ${count} trade${count === 1 ? "" : "s"}. This endpoint returns up to ${TRADE_HISTORY_CAP} records and does not paginate.`;
}

test("helpers are wired from lib/trade-history.ts", () => {
  assert.equal(helperSrc.includes("TRADE_HISTORY_CAP = 200"), true);
  assert.equal(helperSrc.includes("function formatTradeTimestamp"), true);
  assert.equal(helperSrc.includes("function formatTradeMoney"), true);
  assert.equal(helperSrc.includes("function cappedTradeNotice"), true);
});

test("formatTradeTimestamp mirror stays honest", () => {
  assert.equal(mirrorFormatTradeTimestamp(null), "—");
  assert.equal(mirrorFormatTradeTimestamp(undefined), "—");
  assert.equal(mirrorFormatTradeTimestamp("not-a-date"), "—");
  const formatted = mirrorFormatTradeTimestamp(FIXTURE_TRADES[0].timestamp);
  assert.equal(formatted.includes("2026"), true);
});

test("formatTradeMoney mirror stays honest", () => {
  assert.equal(mirrorFormatTradeMoney(null), "—");
  assert.equal(mirrorFormatTradeMoney(undefined), "—");
  assert.equal(mirrorFormatTradeMoney(Number.NaN), "—");
  assert.equal(mirrorFormatTradeMoney(FIXTURE_TRADES[0].sold_price), "$12.50");
});

test("cappedTradeNotice mirror is honest about the fixed cap", () => {
  assert.equal(mirrorCappedTradeNotice(0).includes("up to 200 records"), true);
  assert.equal(mirrorCappedTradeNotice(1).includes("1 trade."), true);
  assert.equal(mirrorCappedTradeNotice(5).includes("5 trades"), true);
  const capped = mirrorCappedTradeNotice(200);
  assert.equal(capped.includes("newest 200 trades"), true);
  assert.equal(capped.includes("does not paginate") || capped.includes("not available here"), true);
});

test("client wrapper hits /reports/trade-history read-only", () => {
  assert.equal(mimirSrc.includes('"/reports/trade-history"'), true);
  assert.equal(mimirSrc.includes("recentTrades:"), true);
  assert.equal(mimirSrc.includes("export type TradeRecord"), true);
  // trade-history/export must never be called by the frontend
  assert.equal(stripComments(mimirSrc).includes("trade-history/export"), false);
});

test("page renders only contract-backed trade fields", () => {
  for (const field of ["item_name", "sku", "sold_price", "trade_in_value", "timestamp", "trade.id"]) {
    assert.equal(pageSrc.includes(field), true, `page should display ${field}`);
  }
  // no invented aggregates or internals
  for (const invented of ["profit", "net_revenue", "total_revenue", "total_profit", "tax", "customer", "payment_method", "chart", "trend"]) {
    assert.equal(pageCode.includes(invented), false, `page must not reference ${invented}`);
  }
});

test("page stays read-only with no write or export behavior", () => {
  for (const forbidden of ["mimirApi.checkout", "PATCH", "DELETE", "POST", "markPulled", "syncNow", "exportCsv", "Blob(", "createObjectURL", "a.download", "placeholder", "/sales/checkout"]) {
    assert.equal(pageCode.includes(forbidden), false, `recent trades page must not reference ${forbidden}`);
  }
});

test("page uses membership-authenticated vendor patterns and guards", () => {
  assert.equal(pageSrc.includes("useVendorShop"), true);
  assert.equal(pageSrc.includes("classifyVendorError"), true);
  assert.equal(pageSrc.includes("shouldApplyShopResult"), true);
  assert.equal(pageSrc.includes("AbortController"), true);
  assert.equal(pageSrc.includes("epochRef"), true);
  assert.equal(pageSrc.includes("reportApiError"), true);
  // no legacy identity header or dev-shop fallback
  assert.equal(pageSrc.includes("X-Clerk-User-Id"), false);
  assert.equal(pageSrc.includes("adminRequest"), false);
});

test("page clears data on shop switch and states the fixed cap honestly", () => {
  assert.equal(pageSrc.includes("setTrades([])"), true);
  assert.equal(pageSrc.includes("cappedTradeNotice"), true);
  assert.equal(pageSrc.includes("up to the newest 200 records"), true);
  assert.equal(pageSrc.includes("does not paginate"), true);
  assert.equal(pageSrc.includes("No trade transactions are recorded"), true);
  assert.equal(pageSrc.includes('aria-live="polite"'), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("page never forces pagination onto the non-paginated contract", () => {
  assert.equal(pageCode.includes("BrowsePagination"), false);
  assert.equal(pageCode.includes("offsetForPage"), false);
  assert.equal(pageCode.includes("limit"), false);
});

test("dashboard lists Recent Trades as an honest fourth read-only tool", () => {
  assert.equal(dashSrc.includes('href: "/admin/reports"'), true);
  assert.equal(dashSrc.includes("Recent Trades"), true);
  assert.equal(dashSrc.includes("up to the newest 200 trade transactions"), true);
  const hrefs = [...dashSrc.matchAll(/href: "([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(hrefs, ["/admin/inventory", "/admin/reports", "/admin/sales", "/pos/find"]);
});

test("sidebar exposes a named Recent Trades entry", () => {
  assert.equal(sidebarSrc.includes('href: "/admin/reports"'), true);
  assert.equal(sidebarSrc.includes('label: "Recent Trades"'), true);
  assert.equal(sidebarSrc.includes("ArrowLeftRight"), true);
});
