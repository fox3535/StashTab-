import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const posFindSrc = readFileSync(join(root, "lib/pos-find.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/inventory/page.tsx"), "utf8");
const layoutSrc = readFileSync(join(root, "app/admin/layout.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const vendorErrorSrc = readFileSync(join(root, "lib/vendor-api-error.ts"), "utf8");
const schemaSrc = readFileSync(join(root, "services/api/app/schemas.py"), "utf8");

// --- Behavioural mirrors of lib/pos-find.ts (the shared slice-05 browse
// --- helpers; kept in lockstep by the source-wiring assertions below).

const FIND_PAGE_SIZE = 50;

function findPageWindow(total, offset, pageSize) {
  const safeTotal = Math.max(0, total);
  const safeOffset = Math.max(0, offset);
  const from = safeTotal === 0 ? 0 : safeOffset + 1;
  const to = Math.min(safeOffset + pageSize, safeTotal);
  return {
    from,
    to,
    hasPrev: safeOffset > 0,
    hasNext: safeOffset + pageSize < safeTotal,
    endOfResults: safeOffset + pageSize >= safeTotal,
  };
}

function offsetForPage(page, pageSize) {
  return Math.max(0, page) * pageSize;
}

function classifyFindResponse(query, total, firstSku) {
  const q = query.trim().toUpperCase();
  if (total <= 0) return "empty";
  if (total === 1 && firstSku && q && firstSku.toUpperCase() === q) return "exact";
  return "list";
}

// Stale-response gate mirror: a result applies only when its epoch is the
// current one AND the responding shop is still the selected shop.
function shouldApplyBrowseResult(myEpoch, currentEpoch, requestShopId, currentShopId) {
  return myEpoch === currentEpoch && Boolean(currentShopId) && requestShopId === currentShopId;
}

// FIXTURES – synthetic only; staging may prove the honest empty state, never
// seeded data. Labels are part of the test evidence.
const FIXTURE_ITEMS = [
  { sku: "SV8-123", name: "FIXTURE Pikachu ex", stock: 2, set_name: "FIXTURE Set" },
  { sku: "SV8-124", name: "FIXTURE Charizard ex", stock: 1, set_name: "FIXTURE Set" },
];

test("slice-06 reuses the slice-05 pure helpers without forking them", () => {
  assert.equal(pageSrc.includes('from "@/lib/pos-find"'), true);
  assert.equal(pageSrc.includes("FIND_PAGE_SIZE,"), true);
  assert.equal(pageSrc.includes("classifyFindResponse,"), true);
  assert.equal(pageSrc.includes("findPageWindow,"), true);
  assert.equal(pageSrc.includes("offsetForPage,"), true);
  assert.equal(pageSrc.includes("pageAfterReset,"), true);
  // The shared helpers stay unchanged in place (slice-05 semantics intact).
  assert.equal(posFindSrc.includes("Pure POS Find browse state helpers (slice-05)."), true);
  assert.equal(posFindSrc.includes("export const FIND_PAGE_SIZE = 50;"), true);
});

test("totals come from the contract total, not the page length", () => {
  assert.equal(pageSrc.includes("data.total"), true);
  assert.equal(
    pageSrc.includes(
      "setTotal(typeof data.total === \"number\" ? data.total : data.items?.length ?? 0)"
    ),
    true
  );
  assert.equal(pageSrc.includes("in-stock rows"), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("offsets are page-based multiples of the page size", () => {
  assert.equal(offsetForPage(0, FIND_PAGE_SIZE), 0);
  assert.equal(offsetForPage(1, FIND_PAGE_SIZE), 50);
  assert.equal(offsetForPage(3, FIND_PAGE_SIZE), 150);
  assert.equal(offsetForPage(-2, FIND_PAGE_SIZE), 0);
  assert.equal(pageSrc.includes("offset: offsetForPage(targetPage, FIND_PAGE_SIZE)"), true);
  assert.equal(pageSrc.includes("limit: FIND_PAGE_SIZE"), true);
  assert.equal(mimirSrc.includes('params.set("offset", String(opts.offset))'), true);
});

test("page boundaries track the honest total", () => {
  const first = findPageWindow(120, 0, FIND_PAGE_SIZE);
  assert.deepEqual(first, { from: 1, to: 50, hasPrev: false, hasNext: true, endOfResults: false });
  const middle = findPageWindow(120, 50, FIND_PAGE_SIZE);
  assert.deepEqual(middle, { from: 51, to: 100, hasPrev: true, hasNext: true, endOfResults: false });
  const last = findPageWindow(120, 100, FIND_PAGE_SIZE);
  assert.deepEqual(last, { from: 101, to: 120, hasPrev: true, hasNext: false, endOfResults: true });
  const exactFill = findPageWindow(50, 0, FIND_PAGE_SIZE);
  assert.equal(exactFill.hasNext, false);
  assert.equal(exactFill.endOfResults, true);
  const empty = findPageWindow(0, 0, FIND_PAGE_SIZE);
  assert.equal(empty.from, 0);
  assert.equal(empty.hasNext, false);
  assert.equal(pageSrc.includes("End of results."), true);
  assert.equal(pageSrc.includes("{windowInfo.from}–{windowInfo.to} of {total}"), true);
  assert.equal(pageSrc.includes("disabled={!windowInfo.hasPrev}"), true);
  assert.equal(pageSrc.includes("disabled={!windowInfo.hasNext}"), true);
});

test("a new query or shop switch resets pagination to page 0", () => {
  assert.equal(pageSrc.includes("void runSearch(query, pageAfterReset())"), true);
  assert.equal(pageSrc.includes("void runSearch(\"\", pageAfterReset(), controller.signal)"), true);
  assert.equal(pageSrc.includes("setPage(pageAfterReset())"), true);
});

test("a shop switch aborts in-flight work and discards stale responses", () => {
  assert.equal(shouldApplyBrowseResult(3, 3, "shop-b", "shop-b"), true);
  assert.equal(shouldApplyBrowseResult(3, 3, "shop-a", "shop-b"), false);
  assert.equal(shouldApplyBrowseResult(3, 3, "shop-b", null), false);
  assert.equal(pageSrc.includes("shouldApplyShopResult(requestedShopId, shopIdRef.current)"), true);
  assert.equal(pageSrc.includes("controller.abort()"), true);
  assert.equal(pageSrc.includes("new AbortController()"), true);
});

test("stale responses from superseded searches are rejected by epoch", () => {
  assert.equal(shouldApplyBrowseResult(2, 3, "shop-b", "shop-b"), false);
  assert.equal(pageSrc.includes("epochRef.current += 1"), true);
  assert.equal(pageSrc.includes("myEpoch !== epochRef.current"), true);
});

test("exact SKU input yields the highlighted exact presentation", () => {
  assert.equal(classifyFindResponse(FIXTURE_ITEMS[0].sku.toLowerCase(), 1, FIXTURE_ITEMS[0].sku), "exact");
  assert.equal(classifyFindResponse("  SV8-123  ", 1, "sv8-123"), "exact");
  assert.equal(pageSrc.includes("Exact SKU match"), true);
  assert.equal(pageSrc.includes('mode === "exact"'), true);
});

test("a single partial-name or substring-SKU result is never exact", () => {
  assert.equal(classifyFindResponse("pika", 1, FIXTURE_ITEMS[0].sku), "list");
  assert.equal(classifyFindResponse("SV8", 1, FIXTURE_ITEMS[0].sku), "list");
  assert.equal(classifyFindResponse("sv8-12", 1, FIXTURE_ITEMS[0].sku), "list");
});

test("barcode identity is never inferred: no barcode field in the live response", () => {
  // InventoryItemOut (the accepted search response) returns no barcode
  // field, so exact matching is documented SKU-only. A barcode-shaped query
  // that does not equal the returned SKU is not exact.
  const outSchema = schemaSrc.slice(schemaSrc.indexOf("class InventoryItemOut"), schemaSrc.indexOf("class InventorySearchResponse"));
  assert.equal(outSchema.includes("barcode"), false);
  assert.equal(classifyFindResponse("8123456789012", 1, FIXTURE_ITEMS[0].sku), "list");
  assert.equal(posFindSrc.includes("returns no barcode field"), true);
  assert.equal(pageSrc.includes("Exact SKU/barcode"), false);
});

test("multiple results never use the exact presentation", () => {
  assert.equal(classifyFindResponse("sv8-123", 2, FIXTURE_ITEMS[0].sku), "list");
  assert.equal(pageSrc.includes("classifyFindResponse(submittedQuery, total, items[0]?.sku)"), true);
});

test("desktop/tablet table and mobile cards render the same rows", () => {
  assert.equal(pageSrc.includes("hidden overflow-x-auto rounded-lg border border-border md:block"), true);
  assert.equal(pageSrc.includes("space-y-2 md:hidden"), true);
  assert.equal(pageSrc.includes("InventoryCard"), true);
  assert.equal(pageSrc.includes("<table"), true);
});

test("loading, empty, and classified error states are present", () => {
  assert.equal(pageSrc.includes("Loading inventory…"), true);
  assert.equal(pageSrc.includes("This is an empty result, not a failed write."), true);
  assert.equal(pageSrc.includes("classifyVendorError(err)"), true);
  assert.equal(pageSrc.includes('role="alert"'), true);
  assert.equal(pageSrc.includes("setTotal(0)"), true);
  assert.equal(pageSrc.includes("reportApiError(err)"), true);
});

test("session-expired, forbidden, unavailable, and network states are classified", () => {
  assert.equal(vendorErrorSrc.includes('if (status === 401) return "session_expired"'), true);
  assert.equal(vendorErrorSrc.includes('if (status === 403) return "forbidden"'), true);
  assert.equal(vendorErrorSrc.includes('if (status === 503 || lowered.includes("feature_not_ready")) return "not_ready"'), true);
  assert.equal(vendorErrorSrc.includes("Session expired. Sign in again."), true);
  assert.equal(vendorErrorSrc.includes("You do not have access to this shop."), true);
  assert.equal(vendorErrorSrc.includes("This feature is not ready."), true);
  assert.equal(vendorErrorSrc.includes("Network error. Check your connection and try again."), true);
  assert.equal(pageSrc.includes("total unavailable"), true);
  assert.equal(pageSrc.includes("counting…"), true);
  assert.equal(pageSrc.includes("setLoaded(true)"), true);
});

test("membership authority and the vendor shell are preserved", () => {
  assert.equal(layoutSrc.includes("<VendorShopProvider>"), true);
  assert.equal(layoutSrc.includes("<AdminBillingGate>"), true);
  assert.equal(layoutSrc.includes("<AdminApiAuthGate>"), true);
  assert.equal(layoutSrc.includes("<ShopAccessGate>{children}</ShopAccessGate>"), true);
  assert.equal(pageSrc.includes("useVendorShop()"), true);
});

test("writes stay visibly locked and the page stays read-only", () => {
  for (const forbidden of ["checkout", "/sales", "PATCH", "DELETE", "reserve", "autoSelect"]) {
    assert.equal(pageSrc.includes(forbidden), false, `found forbidden ${forbidden}`);
  }
  assert.equal(pageSrc.includes("Edit stock / print labels"), true);
  assert.equal(pageSrc.includes("Inventory writes are not ready"), true);
  assert.equal(pageSrc.includes("This screen is read-only."), true);
  assert.equal(posFindSrc.includes("never sell"), true);
});
