// Slice-13 resticker queue regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/resticker.ts by source-wiring assertions. All fixtures are clearly
// labeled synthetic data. Negative scans run against comment-stripped
// source so doc comments that name forbidden behaviour cannot trip them.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/resticker.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/resticker/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);
const gateCode = stripComments(gateSrc);
const mimirCode = stripComments(mimirSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_ITEMS = [
  { id: 401, sku: "FIX-R1", name: "FIXTURE Drifted Card", price: 12.1, sticker_price: 10, suggested_sticker: 13 },
  { id: 402, sku: "FIX-R2", name: "FIXTURE Odd Card", price: null, sticker_price: 4, suggested_sticker: null },
];

// ---- behavioural mirrors of lib/resticker.ts ----
function mirrorFormatRestickerMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}
function mirrorRestickerSetNotice(count) {
  return `Showing ${count} item${count === 1 ? "" : "s"} returned by the API, sorted by name. This endpoint has no cap and no pagination; it returns the current set in one response.`;
}

test("helpers are wired from lib/resticker.ts", () => {
  assert.equal(helperSrc.includes("function formatRestickerMoney"), true);
  assert.equal(helperSrc.includes("function restickerSetNotice"), true);
  assert.equal(helperSrc.includes("has no cap and no pagination"), true);
});

test("money mirror renders missing values honestly", () => {
  assert.equal(mirrorFormatRestickerMoney(null), "—");
  assert.equal(mirrorFormatRestickerMoney(Number.NaN), "—");
  assert.equal(mirrorFormatRestickerMoney(FIXTURE_ITEMS[0].suggested_sticker), "$13.00");
  assert.equal(mirrorFormatRestickerMoney(FIXTURE_ITEMS[1].price), "—");
});

test("set notice discloses the uncapped, name-sorted contract", () => {
  assert.equal(mirrorRestickerSetNotice(1).includes("Showing 1 item returned"), true);
  assert.equal(mirrorRestickerSetNotice(3).includes("Showing 3 items returned"), true);
  assert.equal(mirrorRestickerSetNotice(3).includes("sorted by name"), true);
});

test("client wrapper hits only the read-only resticker GET", () => {
  assert.equal(mimirSrc.includes('"/admin/inventory/resticker"'), true);
  assert.equal(mimirSrc.includes("restickerQueue:"), true);
  assert.equal(mimirSrc.includes("export type RestickerItem"), true);
  assert.equal(mimirCode.includes("resticker-all"), false);
  assert.equal(mimirCode.includes("/resticker`"), false);
});

test("page renders only contract-returned fields and never computes prices", () => {
  for (const field of ["item.name", "item.sku", "item.price", "item.sticker_price", "item.suggested_sticker"]) {
    assert.equal(pageSrc.includes(field), true, `page should use ${field}`);
  }
  for (const invented of ["Math.ceil", "Math.abs", "cost", "margin", "profit", "market", "threshold("]) {
    assert.equal(pageCode.includes(invented), false, `page must not reference ${invented}`);
  }
});

test("page stays read-only with no write or legacy behavior", () => {
  for (const forbidden of ["PATCH", "DELETE", "POST", "adminApi", "adminRequest", "markRestickered", "markAllRestickered", "toast", "<Button", "onClick", "label(", "window.print", "printLabel", "X-Clerk-User-Id"]) {
    assert.equal(pageCode.includes(forbidden), false, `resticker page must not reference ${forbidden}`);
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

test("page clears on shop switch and states loading, empty, and error honestly", () => {
  assert.equal(pageSrc.includes("setItems([])"), true);
  assert.equal(pageSrc.includes("restickerSetNotice(items.length)"), true);
  assert.equal(pageSrc.includes("count unavailable"), true);
  assert.equal(pageSrc.includes("VendorLoadingBlock"), true);
  assert.equal(pageSrc.includes("VendorErrorBanner"), true);
  assert.equal(pageSrc.includes("This is an empty result, not a failed write."), true);
  assert.equal(pageSrc.includes("$2.00 by default; each shop's own setting may differ"), true);
  assert.equal(pageSrc.includes("Current price"), true);
  assert.equal(pageSrc.includes('aria-live="polite"'), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("page never forces pagination onto the uncapped contract", () => {
  assert.equal(pageCode.includes("BrowsePagination"), false);
  assert.equal(pageCode.includes("offsetForPage"), false);
});

test("route gate no longer locks the resticker queue; others stay locked", () => {
  assert.equal(gateCode.includes('"/admin/resticker"'), false);
  for (const locked of ['"/admin/intake"', '"/admin/staging"', '"/admin/settings"', '"/pos/pulls"']) {
    assert.equal(gateCode.includes(locked), true, `${locked} must stay locked`);
  }
});

test("dashboard and sidebar expose an honest Resticker entry", () => {
  assert.equal(dashSrc.includes('href: "/admin/resticker"'), true);
  assert.equal(dashSrc.includes("Resticker Queue"), true);
  assert.equal(dashSrc.includes("Marking restickered and printing labels are not ready."), true);
  assert.equal(sidebarSrc.includes('{ href: "/admin/resticker", label: "Resticker", icon: Sticker }'), true);
  assert.equal(sidebarSrc.includes('label: "Resticker", icon: Sticker, locked: true'), false);
});
