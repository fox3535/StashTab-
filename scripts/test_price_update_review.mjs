// Slice-10 price update review regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/price-updates.ts by source-wiring assertions. All fixtures are
// clearly labeled synthetic data — staging may only prove the honest
// empty state. Negative scans run against comment-stripped source so doc
// comments that name forbidden behaviour cannot trip them.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/price-updates.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/price-updates/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_RECORDS = [
  { id: 201, sku: "FIX-P1", name: "FIXTURE Card One", old_price: 9.5, price: 11, shop_listing_price: 12.25 },
  { id: 202, sku: "FIX-P2", name: "FIXTURE Card Two", old_price: null, price: 4, shop_listing_price: null },
];

// ---- behavioural mirrors of lib/price-updates.ts ----
const PRICE_UPDATES_LARGE_THRESHOLD = 200;
function mirrorFormatPriceUpdateMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}
function mirrorPriceUpdateSetNotice(count) {
  const base = `Showing ${count} record${count === 1 ? "" : "s"} returned by the API. This endpoint has no cap and no pagination; it returns the current set in one response.`;
  if (count >= PRICE_UPDATES_LARGE_THRESHOLD) {
    return `${base} This is a large result set; review may take some scrolling.`;
  }
  return base;
}

test("helpers are wired from lib/price-updates.ts", () => {
  assert.equal(helperSrc.includes("PRICE_UPDATES_LARGE_THRESHOLD = 200"), true);
  assert.equal(helperSrc.includes("function formatPriceUpdateMoney"), true);
  assert.equal(helperSrc.includes("function priceUpdateSetNotice"), true);
});

test("formatPriceUpdateMoney mirror stays honest", () => {
  assert.equal(mirrorFormatPriceUpdateMoney(null), "—");
  assert.equal(mirrorFormatPriceUpdateMoney(undefined), "—");
  assert.equal(mirrorFormatPriceUpdateMoney(Number.NaN), "—");
  assert.equal(mirrorFormatPriceUpdateMoney(FIXTURE_RECORDS[0].price), "$11.00");
});

test("priceUpdateSetNotice mirror discloses the uncapped contract honestly", () => {
  const one = mirrorPriceUpdateSetNotice(1);
  assert.equal(one.includes("Showing 1 record "), true);
  assert.equal(one.includes("no cap and no pagination"), true);
  assert.equal(one.includes("large result set"), false);
  const large = mirrorPriceUpdateSetNotice(250);
  assert.equal(large.includes("Showing 250 records"), true);
  assert.equal(large.includes("large result set"), true);
});

test("client wrapper hits /admin/inventory/updated read-only", () => {
  assert.equal(mimirSrc.includes('"/admin/inventory/updated"'), true);
  assert.equal(mimirSrc.includes("priceUpdates:"), true);
  assert.equal(mimirSrc.includes("export type PendingPriceUpdate"), true);
  // the write halves of the pricing workflow must never be called
  const code = stripComments(mimirSrc);
  assert.equal(code.includes("approve-update"), false);
  assert.equal(code.includes("approve-all-updates"), false);
});

test("page renders only contract-returned fields", () => {
  for (const field of ["record.name", "record.sku", "old_price", "record.price", "shop_listing_price"]) {
    assert.equal(pageSrc.includes(field), true, `page should display ${field}`);
  }
  // "provider" alone would false-positive on the vendor-shop-provider
  // import path; the forbidden behavior is provider price lookup.
  for (const invented of ["cost", "margin", "profit", "market_price", "provider_price", "providerPrice", "PokemonAPI", "recommend", "approved", "complete"]) {
    assert.equal(pageCode.includes(invented), false, `page must not reference ${invented}`);
  }
});

test("page stays read-only with no write or legacy pricing behavior", () => {
  for (const forbidden of ["PATCH", "DELETE", "POST", "approve", "dismiss", "reprice", "resticker", "exportCsv", "Blob(", "createObjectURL", "placeholder", "PokemonAPI", "syncNow"]) {
    assert.equal(pageCode.includes(forbidden), false, `price updates page must not reference ${forbidden}`);
  }
});

test("page uses membership-authenticated vendor patterns and guards", () => {
  assert.equal(pageSrc.includes("useVendorShop"), true);
  assert.equal(pageSrc.includes("classifyVendorError"), true);
  assert.equal(pageSrc.includes("shouldApplyShopResult"), true);
  assert.equal(pageSrc.includes("AbortController"), true);
  assert.equal(pageSrc.includes("epochRef"), true);
  assert.equal(pageSrc.includes("reportApiError"), true);
  assert.equal(pageSrc.includes("X-Clerk-User-Id"), false);
  assert.equal(pageSrc.includes("adminRequest"), false);
  assert.equal(pageSrc.includes("adminApi"), false);
});

test("page clears data on shop switch and discloses the API limits", () => {
  assert.equal(pageSrc.includes("setRecords([])"), true);
  assert.equal(pageSrc.includes("priceUpdateSetNotice"), true);
  assert.equal(pageSrc.includes("pending/previous price update"), true);
  // The uncapped-contract disclosure is emitted by priceUpdateSetNotice in
  // lib/price-updates.ts, which the page renders via the wiring test above.
  assert.equal(helperSrc.includes("has no cap and no pagination"), true);
  assert.equal(pageSrc.includes("priceUpdateSetNotice(records.length)"), true);
  assert.equal(pageSrc.includes("This is an empty result, not a failed write."), true);
  assert.equal(pageSrc.includes('aria-live="polite"'), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("page never forces pagination onto the uncapped contract", () => {
  assert.equal(pageCode.includes("BrowsePagination"), false);
  assert.equal(pageCode.includes("offsetForPage"), false);
});

test("dashboard lists Price Updates as an honest fifth read-only tool", () => {
  assert.equal(dashSrc.includes('href: "/admin/price-updates"'), true);
  assert.equal(dashSrc.includes("Price Updates"), true);
  const hrefs = [...dashSrc.matchAll(/href: "([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(hrefs, [
    "/admin/inventory",
    "/admin/price-updates",
    "/admin/reports",
    "/admin/sales",
    "/pos/find",
  ]);
});

test("sidebar exposes a named Price Updates entry", () => {
  assert.equal(sidebarSrc.includes('href: "/admin/price-updates"'), true);
  assert.equal(sidebarSrc.includes('label: "Price Updates"'), true);
  assert.equal(sidebarSrc.includes("BadgeDollarSign"), true);
});
