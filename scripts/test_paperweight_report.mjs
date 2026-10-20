// Slice-12 paperweight report regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/paperweight.ts by source-wiring assertions. All fixtures are
// clearly labeled synthetic data. Negative scans run against
// comment-stripped source so doc comments that name forbidden behaviour
// cannot trip them.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/paperweight.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/paperweight/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);
const gateCode = stripComments(gateSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_ITEMS = [
  { id: 301, sku: "FIX-W1", name: "FIXTURE Old Card", stock: 2, price: 7.5, date_added: "2026-06-01T15:30:00+00:00" },
  { id: 302, sku: "FIX-W2", name: "FIXTURE Older Card", stock: 1, price: 3, date_added: null },
];

// ---- behavioural mirrors of lib/paperweight.ts ----
const PAPERWEIGHT_LIST_CAP = 100;
function mirrorFormatPaperweightMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}
function mirrorFormatPaperweightDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toISOString().slice(0, 10);
}
function mirrorPaperweightListNotice(itemCount, units) {
  const shown = `Showing ${itemCount} item${itemCount === 1 ? "" : "s"}, oldest first. The ${units} unit total counts every qualifying item.`;
  if (itemCount >= PAPERWEIGHT_LIST_CAP) {
    return `${shown} The API returns at most the ${PAPERWEIGHT_LIST_CAP} oldest items, so more may exist than are listed here.`;
  }
  return shown;
}

test("helpers are wired from lib/paperweight.ts", () => {
  assert.equal(helperSrc.includes("PAPERWEIGHT_LIST_CAP = 100"), true);
  assert.equal(helperSrc.includes("function formatPaperweightMoney"), true);
  assert.equal(helperSrc.includes("function formatPaperweightDate"), true);
  assert.equal(helperSrc.includes("function paperweightListNotice"), true);
  assert.equal(helperSrc.includes("toISOString().slice(0, 10)"), true);
  assert.equal(helperSrc.includes("so more may exist than are listed here."), true);
});

test("money and date mirrors render missing values honestly", () => {
  assert.equal(mirrorFormatPaperweightMoney(null), "—");
  assert.equal(mirrorFormatPaperweightMoney(Number.NaN), "—");
  assert.equal(mirrorFormatPaperweightMoney(FIXTURE_ITEMS[0].price), "$7.50");
  assert.equal(mirrorFormatPaperweightDate(FIXTURE_ITEMS[0].date_added), "2026-06-01");
  assert.equal(mirrorFormatPaperweightDate(FIXTURE_ITEMS[1].date_added), "—");
  assert.equal(mirrorFormatPaperweightDate("not a date"), "—");
});

test("list notice discloses the 100-item cap only when it may apply", () => {
  const small = mirrorPaperweightListNotice(1, 3);
  assert.equal(small.includes("Showing 1 item,"), true);
  assert.equal(small.includes("The 3 unit total counts every qualifying item."), true);
  assert.equal(small.includes("at most the 100 oldest"), false);
  const capped = mirrorPaperweightListNotice(100, 420);
  assert.equal(capped.includes("Showing 100 items"), true);
  assert.equal(capped.includes("at most the 100 oldest items"), true);
});

test("client wrapper hits /admin/inventory/paperweight read-only", () => {
  assert.equal(mimirSrc.includes('"/admin/inventory/paperweight"'), true);
  assert.equal(mimirSrc.includes("paperweightReport:"), true);
  assert.equal(mimirSrc.includes("export type PaperweightItem"), true);
  assert.equal(mimirSrc.includes("export type PaperweightReport"), true);
});

test("page renders only contract-returned fields", () => {
  for (const field of ["item.name", "item.sku", "item.stock", "item.price", "item.date_added", "data.units"]) {
    assert.equal(pageSrc.includes(field), true, `page should use ${field}`);
  }
  for (const invented of ["cost", "margin", "profit", "market_price", "suggested", "discount(", "paperweight_days", "daysOld", "ageDays"]) {
    assert.equal(pageCode.includes(invented), false, `page must not reference ${invented}`);
  }
});

test("page stays read-only with no write or legacy behavior", () => {
  for (const forbidden of ["PATCH", "DELETE", "POST", "adminApi", "adminRequest", "listPaperweight", "/admin/settings", "exportCsv", "Blob(", "createObjectURL", "X-Clerk-User-Id", "<Button", "onClick"]) {
    assert.equal(pageCode.includes(forbidden), false, `paperweight page must not reference ${forbidden}`);
  }
});

test("page uses membership-authenticated vendor patterns and guards", () => {
  assert.equal(pageSrc.includes("useVendorShop"), true);
  assert.equal(pageSrc.includes("classifyVendorError"), true);
  assert.equal(pageSrc.includes("shouldApplyShopResult"), true);
  assert.equal(pageSrc.includes("AbortController"), true);
  assert.equal(pageSrc.includes("epochRef"), true);
  assert.equal(pageSrc.includes("reportApiError"), true);
});

test("page clears data on shop switch and states loading, empty, and error honestly", () => {
  assert.equal(pageSrc.includes("setItems([])"), true);
  assert.equal(pageSrc.includes("setUnits(null)"), true);
  assert.equal(pageSrc.includes("paperweightListNotice(items.length, units)"), true);
  assert.equal(pageSrc.includes("units unavailable"), true);
  assert.equal(pageSrc.includes("VendorLoadingBlock"), true);
  assert.equal(pageSrc.includes("VendorErrorBanner"), true);
  assert.equal(pageSrc.includes("No in-stock items are past this shop's paperweight cutoff right now."), true);
  assert.equal(pageSrc.includes("60 days by default; each shop's own setting may differ"), true);
  assert.equal(pageSrc.includes('aria-live="polite"'), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("page never forces pagination onto the capped contract", () => {
  assert.equal(pageCode.includes("BrowsePagination"), false);
  assert.equal(pageCode.includes("offsetForPage"), false);
});

test("route gate no longer locks the paperweight report; others stay locked", () => {
  assert.equal(gateCode.includes('"/admin/paperweight"'), false);
  for (const locked of ['"/admin/intake"', '"/admin/resticker"', '"/admin/settings"', '"/pos/pulls"']) {
    assert.equal(gateCode.includes(locked), true, `${locked} must stay locked`);
  }
});

test("dashboard and sidebar expose an honest Paperweight entry", () => {
  assert.equal(dashSrc.includes('href: "/admin/paperweight"'), true);
  assert.equal(dashSrc.includes("Paperweight Report"), true);
  assert.equal(dashSrc.includes("Discounting and relisting are not ready."), true);
  assert.equal(sidebarSrc.includes('{ href: "/admin/paperweight", label: "Paperweight", icon: Hourglass }'), true);
  assert.equal(sidebarSrc.includes('label: "Paperweight", icon: PackageSearch, locked: true'), false);
});
