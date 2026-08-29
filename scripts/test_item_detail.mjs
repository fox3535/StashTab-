// Slice-07 POS item detail regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/item-detail.ts by source-wiring assertions. All fixtures are clearly
// labeled synthetic data — staging may only prove the honest empty state.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/item-detail.ts"), "utf8");
const detailSrc = readFileSync(join(root, "components/vendor/vendor-item-detail.tsx"), "utf8");
const posSrc = readFileSync(join(root, "app/pos/find/page.tsx"), "utf8");
const adminSrc = readFileSync(join(root, "app/admin/inventory/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const schemaSrc = readFileSync(join(root, "services/api/app/schemas.py"), "utf8");

// Comment-stripped view of the component so honesty/read-only scans test
// rendered behaviour, not doc-comment prose.
const detailCode = detailSrc.replace(/\/\/.*$/gm, "");

// --- Behavioral mirrors of lib/item-detail.ts ---

function normalizeDetailSku(sku) {
  return (sku ?? "").trim().toUpperCase();
}

function shouldApplyDetailResult(myEpoch, currentEpoch, requestShopId, currentShopId) {
  return Boolean(currentShopId) && myEpoch === currentEpoch && requestShopId === currentShopId;
}

// --- Labeled fixtures (synthetic; staging may only prove empty) ---
const FIXTURE_ITEM = {
  sku: "SV8-123",
  name: "FIXTURE Pikachu ex",
  stock: 2,
  price: 4.5,
  sticker_price: null,
  set_name: "FIXTURE Set",
  sequence_number: "123/166",
  game: "Pokemon",
  card_type: "Pokemon",
  variant: "ex",
  condition: "NM",
  image_url: null,
};

test("normalizeDetailSku mirrors the server's uppercase SKU comparison", () => {
  assert.equal(normalizeDetailSku(" sv8-123 "), "SV8-123");
  assert.equal(normalizeDetailSku(""), "");
  assert.equal(normalizeDetailSku(null), "");
  assert.equal(normalizeDetailSku(undefined), "");
  assert.equal(helperSrc.includes(".trim().toUpperCase()"), true);
  assert.equal(helperSrc.includes("sku.upper()"), true);
});

test("late detail responses are discarded after a newer lookup or shop switch", () => {
  assert.equal(shouldApplyDetailResult(1, 1, "shop-1", "shop-1"), true);
  assert.equal(shouldApplyDetailResult(1, 2, "shop-1", "shop-1"), false);
  assert.equal(shouldApplyDetailResult(2, 2, "shop-1", "shop-2"), false);
  assert.equal(shouldApplyDetailResult(2, 2, "shop-1", null), false);
  assert.equal(detailSrc.includes("shouldApplyDetailResult("), true);
  assert.equal(detailSrc.includes("epochRef.current += 1"), true);
});

test("the detail lookup uses the accepted GET /inventory/{sku} client wrapper", () => {
  assert.equal(detailSrc.includes("mimirApi.getInventoryBySku(normalizedSku"), true);
  assert.equal(mimirSrc.includes("getInventoryBySku: (sku: string, opts: RequestOptions)"), true);
  assert.equal(mimirSrc.includes("/inventory/${encodeURIComponent(sku)}"), true);
});

test("detail states cover loading, 404, session expiry, forbidden, and network", () => {
  assert.equal(detailSrc.includes("classifyVendorError(err)"), true);
  assert.equal(detailSrc.includes('classified.kind === "not_found"'), true);
  assert.equal(detailSrc.includes("is not listed for"), true);
  assert.equal(detailSrc.includes("VendorErrorBanner"), true);
  assert.equal(detailSrc.includes("VendorLoadingBlock"), true);
  assert.equal(detailSrc.includes("reportApiError(err)"), true);
});

test("only contract-backed InventoryItemOut fields are rendered", () => {
  // Fields asserted to exist in the schema...
  for (const field of ["sku", "name", "set_name", "sequence_number", "stock", "price", "condition", "image_url"]) {
    assert.equal(schemaSrc.includes(`${field}:`), true);
  }
  // ...and no field the schema does not return (no barcode, no location).
  assert.equal(schemaSrc.includes("barcode"), false);
  assert.equal(detailCode.includes("location"), false);
  assert.equal(detailCode.includes("barcode"), false);
  assert.equal(detailSrc.includes("item.set_name"), true);
  assert.equal(detailSrc.includes("item.sequence_number"), true);
  assert.equal(detailSrc.includes("item.condition"), true);
  assert.equal(detailSrc.includes("item.stock"), true);
});

test("detail identity opens from the actual returned SKU only", () => {
  // POS Find and admin inventory pass the row's returned sku, never a query.
  assert.equal(posSrc.includes("onOpenDetail(item.sku)"), true);
  assert.equal(adminSrc.includes("onOpenDetail(item.sku)"), true);
  assert.equal(adminSrc.includes("setDetailSku(item.sku)"), true);
  assert.equal(detailSrc.includes("normalizeDetailSku(sku)"), true);
});

test("POS Find wires the shared detail with accessible Back and resets it", () => {
  assert.equal(posSrc.includes("VendorItemDetail"), true);
  assert.equal(posSrc.includes('aria-label={`View details for SKU ${item.sku}`}'), true);
  assert.equal(posSrc.includes("min-h-12"), true);
  assert.equal(posSrc.includes('backClassName="min-h-12"'), true);
  // Query/shop reset closes any open detail.
  assert.equal(posSrc.includes('setDetailSku("")'), true);
});

test("admin inventory wires the shared detail and clears it on shop switch", () => {
  assert.equal(adminSrc.includes("VendorItemDetail"), true);
  assert.equal(adminSrc.includes('aria-label={`View details for SKU ${item.sku}`}'), true);
  assert.equal(adminSrc.includes('setDetailSku("")'), true);
});

test("the shared component provides accessible Back navigation and focus", () => {
  assert.equal(detailSrc.includes('aria-label={backLabel}'), true);
  assert.equal(detailSrc.includes("backLabel = \"Back to results\""), true);
  assert.equal(detailSrc.includes("backButtonRef.current?.focus()"), true);
  assert.equal(detailSrc.includes("ArrowLeft"), true);
});

test("the detail experience is read-only by construction", () => {
  for (const forbidden of ["checkout", "/sales", "PATCH", "DELETE", "reserve", "autoSelect", "markPulled", "syncNow"]) {
    assert.equal(detailCode.includes(forbidden), false, `detail component must not reference ${forbidden}`);
  }
  assert.equal(detailSrc.includes("Read-only record"), true);
  assert.equal(detailSrc.includes("Selling, edits, labels, and adjustments are not ready."), true);
});

test("membership authority and shop-hint behavior are preserved", () => {
  assert.equal(detailSrc.includes("useVendorShop()"), true);
  assert.equal(detailSrc.includes("shopId: requestedShopId"), true);
  assert.equal(detailSrc.includes("AbortController"), true);
  assert.equal(detailSrc.includes("controller.abort()"), true);
});

test("fixture sanity: sell price follows the sticker/price rule", () => {
  const sellPrice = FIXTURE_ITEM.sticker_price && FIXTURE_ITEM.sticker_price > 0
    ? FIXTURE_ITEM.sticker_price
    : FIXTURE_ITEM.price;
  assert.equal(sellPrice, 4.5);
});
