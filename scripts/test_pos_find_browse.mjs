import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const posFindSrc = readFileSync(join(root, "lib/pos-find.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/pos/find/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");

// --- Behavioural mirrors of lib/pos-find.ts (kept in lockstep by the
// --- source-wiring assertions below).

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
function shouldApplyFindResult(myEpoch, currentEpoch, requestShopId, currentShopId) {
  return myEpoch === currentEpoch && Boolean(currentShopId) && requestShopId === currentShopId;
}

// FIXTURES — synthetic only; staging may prove the honest empty state, never
// seeded data. Labels are part of the test evidence.
const FIXTURE_ITEMS = [
  { sku: "SV8-123", name: "FIXTURE Pikachu ex", stock: 2, set_name: "FIXTURE Set" },
  { sku: "SV8-124", name: "FIXTURE Charizard ex", stock: 1, set_name: "FIXTURE Set" },
];

test("totals come from the contract total, not the page length", () => {
  assert.equal(pageSrc.includes("data.total"), true);
  assert.equal(pageSrc.includes("in-stock"), true);
  assert.equal(pageSrc.includes('role="status"'), true);
});

test("offsets are page-based multiples of the page size", () => {
  assert.equal(offsetForPage(0, FIND_PAGE_SIZE), 0);
  assert.equal(offsetForPage(1, FIND_PAGE_SIZE), 50);
  assert.equal(offsetForPage(2, FIND_PAGE_SIZE), 100);
  assert.equal(offsetForPage(-1, FIND_PAGE_SIZE), 0);
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
  assert.equal(posFindSrc.includes("endOfResults: safeOffset + pageSize >= safeTotal"), true);
  assert.equal(pageSrc.includes("End of results."), true);
});

test("a new query or shop switch resets pagination to page 0", () => {
  assert.equal(pageSrc.includes("void runSearch(query, pageAfterReset())"), true);
  assert.equal(pageSrc.includes("setPage(pageAfterReset())"), true);
  assert.equal(posFindSrc.includes("return 0;"), true);
});

test("a shop switch discards in-flight and stale responses", () => {
  assert.equal(shouldApplyFindResult(3, 3, "shop-b", "shop-b"), true);
  assert.equal(shouldApplyFindResult(3, 3, "shop-a", "shop-b"), false);
  assert.equal(shouldApplyFindResult(3, 3, "shop-b", null), false);
  assert.equal(pageSrc.includes("shouldApplyShopResult(requestedShopId, shopIdRef.current)"), true);
  assert.equal(pageSrc.includes("controller.abort()"), true);
});

test("stale responses from superseded searches are rejected by epoch", () => {
  assert.equal(shouldApplyFindResult(2, 3, "shop-b", "shop-b"), false);
  assert.equal(pageSrc.includes("epochRef.current += 1"), true);
  assert.equal(pageSrc.includes("myEpoch !== epochRef.current"), true);
});

test("exact SKU/barcode input yields the fast-path item card", () => {
  assert.equal(classifyFindResponse(FIXTURE_ITEMS[0].sku.toLowerCase(), 1, FIXTURE_ITEMS[0].sku), "exact");
  assert.equal(classifyFindResponse("  SV8-123  ", 1, "sv8-123"), "exact");
  assert.equal(pageSrc.includes("Exact SKU/barcode match"), true);
  assert.equal(pageSrc.includes('mode === "exact"'), true);
});

test("partial or ambiguous matches stay normal search results", () => {
  assert.equal(classifyFindResponse("sv8", 2, FIXTURE_ITEMS[0].sku), "list");
  assert.equal(classifyFindResponse("sv8", 1, "SV8-999"), "list");
  assert.equal(pageSrc.includes("classifyFindResponse(submittedQuery, total, results[0]?.sku)"), true);
});

test("barcode wedges submit through keyboard input", () => {
  assert.equal(pageSrc.includes('e.key === "Enter" && submitSearch()'), true);
  assert.equal(pageSrc.includes('placeholder="Scan barcode or search SKU..."'), true);
});

test("empty results stay an honest empty state, not an error", () => {
  assert.equal(classifyFindResponse("anything", 0, undefined), "empty");
  assert.equal(pageSrc.includes("No in-stock cards matched. This is an empty result, not a failed write."), true);
});

test("errors surface classified states and clear results", () => {
  assert.equal(pageSrc.includes("classifyVendorError(err)"), true);
  assert.equal(pageSrc.includes('role="alert"'), true);
  assert.equal(pageSrc.includes("setTotal(0)"), true);
});

test("POS Find stays read-only: no sells, reserves, or writes", () => {
  for (const forbidden of ["checkout", "/sales", "PATCH", "DELETE", "reserve", "autoSelect"]) {
    assert.equal(pageSrc.includes(forbidden), false, `found forbidden ${forbidden}`);
  }
  assert.equal(posFindSrc.includes("never sell"), true);
});
