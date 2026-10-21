// Slice-14 dashboard metrics regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/dashboard-metrics.ts by source-wiring assertions. Owner decisions
// D1–D4 (docs/frontend-recovery-v1/PLAN-SLICE-14-DASHBOARD-METRICS.md)
// limit the dashboard to three inventory figures. Fixtures are labeled
// synthetic data. Negative scans run against comment-stripped source.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/dashboard-metrics.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const planSrc = readFileSync(join(root, "docs/frontend-recovery-v1/PLAN-SLICE-14-DASHBOARD-METRICS.md"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);
const mimirCode = stripComments(mimirSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_METRICS = { inventory_count: 1284, inventory_value: 18420.5, paperweight_units: 12 };

// ---- behavioural mirrors of lib/dashboard-metrics.ts ----
const countFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const moneyFormat = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const isFiniteNumber = (v) => typeof v === "number" && Number.isFinite(v);
const mirrorCount = (v) => (isFiniteNumber(v) ? countFormat.format(v) : "—");
const mirrorMoney = (v) => (isFiniteNumber(v) ? moneyFormat.format(v) : "—");
const mirrorPositive = (v) => isFiniteNumber(v) && v > 0;

test("helpers are wired from lib/dashboard-metrics.ts", () => {
  for (const name of ["function formatMetricCount", "function formatMetricMoney", "function isPositiveMetric", "Number.isFinite(value)"]) {
    assert.equal(helperSrc.includes(name), true, `helper source should contain ${name}`);
  }
  assert.equal(helperSrc.includes('currency: "USD"'), true);
});

test("formatters render real numbers and never turn missing data into zero", () => {
  assert.equal(mirrorCount(FIXTURE_METRICS.inventory_count), "1,284");
  assert.equal(mirrorMoney(FIXTURE_METRICS.inventory_value), "$18,420.50");
  assert.equal(mirrorCount(0), "0");
  assert.equal(mirrorMoney(0), "$0.00");
  for (const missing of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY, "12"]) {
    assert.equal(mirrorCount(missing), "—");
    assert.equal(mirrorMoney(missing), "—");
  }
});

test("ember warning only for a real positive stagnant count", () => {
  assert.equal(mirrorPositive(FIXTURE_METRICS.paperweight_units), true);
  assert.equal(mirrorPositive(0), false);
  assert.equal(mirrorPositive(null), false);
  assert.equal(pageSrc.includes('stagnantWarn ? "text-ember" : "text-foreground"'), true);
});

test("client wrapper is GET-only and types only the three allowed fields", () => {
  assert.equal(mimirSrc.includes('mimirFetch<DashboardMetrics>("/admin/dashboard", opts)'), true);
  const typeBlock = mimirSrc.slice(mimirSrc.indexOf("export type DashboardMetrics"));
  const body = typeBlock.slice(0, typeBlock.indexOf("};"));
  for (const field of ["inventory_count", "inventory_value", "paperweight_units"]) {
    assert.equal(body.includes(field), true, `DashboardMetrics should type ${field}`);
  }
  // Scoped to the DashboardMetrics type: show P&L elsewhere in mimir-api
  // legitimately has its own total_revenue field.
  for (const hidden of ["total_revenue", "sale_count", "staging_count", "pending_sync"]) {
    assert.equal(body.includes(hidden), false, `DashboardMetrics must not type ${hidden}`);
  }
  assert.equal(mimirCode.includes("staging_count"), false);
  assert.equal(mimirCode.includes("pending_sync"), false);
});

test("page renders exactly the three decided tiles with honest captions", () => {
  for (const text of ["In-stock items", "SKUs with stock &gt; 0", "Inventory value", "At current sell price, not cost", "Stagnant units", 'href="/admin/paperweight"']) {
    assert.equal(pageSrc.includes(text), true, `page should include ${text}`);
  }
  for (const hidden of ["total_revenue", "sale_count", "staging_count", "pending_sync", "profit", "margin"]) {
    assert.equal(pageCode.includes(hidden), false, `page must not reference ${hidden}`);
  }
});

test("loading and error show a dash, never a fake zero, and never hide the tool cards", () => {
  assert.equal(pageSrc.includes("const shown = loading || errorText ? null : metrics;"), true);
  assert.equal(pageSrc.includes("formatMetricCount(shown?.inventory_count)"), true);
  assert.equal(pageSrc.includes("formatMetricMoney(shown?.inventory_value)"), true);
  assert.equal(pageSrc.includes("Inventory metrics are unavailable right now."), true);
  // Ready and deferred sections render unconditionally after the metrics.
  assert.equal(pageSrc.includes('aria-label="Ready tools"'), true);
  assert.equal(pageSrc.includes('aria-label="Deferred tools"'), true);
  assert.equal(/errorText\s*\?\s*null\s*:\s*\(\s*<section aria-label="Ready tools"/.test(pageSrc), false);
});

test("page uses membership-authenticated vendor patterns and guards", () => {
  for (const guard of ["useVendorShop", "classifyVendorError", "shouldApplyShopResult", "AbortController", "epochRef", "reportApiError", "setMetrics(null)", 'aria-live="polite"', 'role="status"']) {
    assert.equal(pageSrc.includes(guard), true, `page should include ${guard}`);
  }
});

test("page is read-only with no write, polling, or legacy behaviour", () => {
  for (const forbidden of ["POST", "PATCH", "DELETE", "adminApi", "adminRequest", "setInterval", "X-Clerk-User-Id", "NEXT_PUBLIC_DEV_SHOP_ID"]) {
    assert.equal(pageCode.includes(forbidden), false, `dashboard must not reference ${forbidden}`);
  }
});

test("phone layout keeps two columns and shrinks the big numbers", () => {
  assert.equal(pageSrc.includes("grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-3"), true);
  assert.equal(pageSrc.includes("text-2xl font-bold tracking-tight md:text-4xl"), true);
  assert.equal(pageSrc.includes("break-words"), true);
  assert.equal(pageSrc.includes("min-h-11"), true);
});

test("plan records the owner decisions this page implements", () => {
  assert.equal(planSrc.includes("PLAN FINAL"), true);
  assert.equal(planSrc.includes("**D2:** (a) omit `total_revenue` and `sale_count`"), true);
});
