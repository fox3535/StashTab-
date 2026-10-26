// Slice-15 read-only staging queue regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/staging-queue.ts by source-wiring assertions. Committing staging is
// the inventory-truth receive path (held F2 work), so these tests also pin
// that no staging write is wired anywhere in the vendor client or page.
// Fixtures are labeled synthetic data. Negative scans run against
// comment-stripped source.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/staging-queue.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/staging/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const thumbSrc = readFileSync(join(root, "app/pos/components/card-thumbnail.tsx"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");
const nextConfigSrc = readFileSync(join(root, "next.config.ts"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);
const mimirCode = stripComments(mimirSrc);
const gateCode = stripComments(gateSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_ROWS = [
  { id: 9, sku: "FIX-ST-1", name: "FIXTURE Gengar", set_name: "FIXTURE Set", sequence_number: "157", market_price: 9.1, suggested_price: 10, quantity: 3, condition: "Near Mint", variant: "Standard", needs_review: true },
  { id: 8, sku: "FIX-ST-2", name: "FIXTURE Gengar", set_name: "FIXTURE Set", sequence_number: "157", market_price: null, suggested_price: null, quantity: 1, condition: "Lightly Played", variant: null, needs_review: false },
];

// ---- behavioural mirrors of lib/staging-queue.ts ----
const STAGING_LIST_CAP = 100;
function mirrorMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}
function mirrorSetLine(setName, sequence) {
  const parts = [setName?.trim(), sequence?.trim() ? `#${sequence.trim()}` : ""].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}
function mirrorConditionLine(condition, variant) {
  const parts = [condition?.trim(), variant?.trim()].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}
function mirrorNotice(count) {
  const shown = `Showing ${count} staged item${count === 1 ? "" : "s"}, newest first.`;
  if (count >= STAGING_LIST_CAP) {
    return `${shown} The API returns at most the ${STAGING_LIST_CAP} newest, so more may be staged than are listed here.`;
  }
  return shown;
}

test("helpers are wired from lib/staging-queue.ts", () => {
  for (const name of ["STAGING_LIST_CAP = 100", "function formatStagingMoney", "function stagingSetLine", "function stagingConditionLine", "function stagingListNotice", "so more may be staged than are listed here."]) {
    assert.equal(helperSrc.includes(name), true, `helper source should contain ${name}`);
  }
});

test("helper mirrors render missing values honestly", () => {
  assert.equal(mirrorMoney(FIXTURE_ROWS[0].market_price), "$9.10");
  assert.equal(mirrorMoney(FIXTURE_ROWS[1].market_price), "—");
  assert.equal(mirrorSetLine("FIXTURE Set", "157"), "FIXTURE Set · #157");
  assert.equal(mirrorSetLine(null, null), "—");
  assert.equal(mirrorSetLine("", "  "), "—");
  assert.equal(mirrorConditionLine("Near Mint", "Standard"), "Near Mint · Standard");
  assert.equal(mirrorConditionLine("Lightly Played", null), "Lightly Played");
  assert.equal(mirrorConditionLine(null, null), "—");
});

test("same card in two conditions stays distinguishable", () => {
  const [a, b] = FIXTURE_ROWS;
  assert.equal(mirrorSetLine(a.set_name, a.sequence_number), mirrorSetLine(b.set_name, b.sequence_number));
  assert.notEqual(mirrorConditionLine(a.condition, a.variant), mirrorConditionLine(b.condition, b.variant));
});

test("cap notice appears only when the 100-newest cap may apply", () => {
  assert.equal(mirrorNotice(1), "Showing 1 staged item, newest first.");
  assert.equal(mirrorNotice(99).includes("at most the 100 newest"), false);
  assert.equal(mirrorNotice(100).includes("at most the 100 newest"), true);
});

test("client wraps only the read-only staging GET and no staging write", () => {
  assert.equal(mimirSrc.includes('mimirFetch<{ items: StagingQueueItem[] }>("/admin/staging", opts)'), true);
  assert.equal(mimirSrc.includes("export type StagingQueueItem"), true);
  for (const write of ["/commit", "commit-all", "/refetch", "apply-trades", "/admin/staging/"]) {
    assert.equal(mimirCode.includes(write), false, `mimir-api must not wrap ${write}`);
  }
  const typeBlock = mimirSrc.slice(mimirSrc.indexOf("export type StagingQueueItem"));
  const body = typeBlock.slice(0, typeBlock.indexOf("};"));
  for (const field of ["condition", "variant", "card_type", "needs_review", "market_price", "suggested_price", "image_url", "quantity"]) {
    assert.equal(body.includes(field), true, `StagingQueueItem should type ${field}`);
  }
  assert.equal(body.includes("cost_basis"), false);
});

test("page renders contract fields, shows condition, and never cost basis", () => {
  for (const field of ["item.name", "item.sku", "item.set_name", "item.sequence_number", "item.condition", "item.variant", "item.quantity", "item.market_price", "item.suggested_price", "item.needs_review", "item.image_url"]) {
    assert.equal(pageSrc.includes(field), true, `page should use ${field}`);
  }
  for (const hidden of ["cost_basis", "barcode_path", "ocr_metadata", "margin", "profit"]) {
    assert.equal(pageCode.includes(hidden), false, `page must not reference ${hidden}`);
  }
  assert.equal(pageSrc.includes("Market price comes from card data and is not your price."), true);
});

test("page has no staging action of any kind", () => {
  for (const forbidden of ["POST", "PATCH", "DELETE", "adminApi", "adminRequest", "commitStaging", "commitAllStaging", "refetchStaging", "deleteStaging", "applyTradesToStaging", "listPendingTrades", "toast", "<Button", "onClick", "<form", "X-Clerk-User-Id"]) {
    assert.equal(pageCode.includes(forbidden), false, `staging page must not reference ${forbidden}`);
  }
  assert.equal(pageSrc.includes("committing to inventory, editing, removing, and applying trades are not ready"), true);
});

test("page uses membership-authenticated vendor patterns and honest states", () => {
  for (const guard of ["useVendorShop", "classifyVendorError", "shouldApplyShopResult", "AbortController", "epochRef", "reportApiError", "setItems([])", "VendorLoadingBlock", "VendorErrorBanner", "count unavailable", 'aria-live="polite"', 'role="status"', "stagingListNotice(items.length)"]) {
    assert.equal(pageSrc.includes(guard), true, `page should include ${guard}`);
  }
  assert.equal(pageSrc.includes("Nothing is waiting in staging for this shop. This is an empty result, not a failed write."), true);
  assert.equal(pageCode.includes("BrowsePagination"), false);
});

test("thumbnails reuse the accepted component with no new image hosts", () => {
  assert.equal(pageSrc.includes('import { CardThumbnail } from "@/app/pos/components/card-thumbnail"'), true);
  assert.equal(thumbSrc.includes("export type ThumbnailSource"), true);
  assert.equal(thumbSrc.includes('Pick<InventoryItem, "name" | "image_url">'), true);
  assert.equal(mimirSrc.includes('getItemImageUrl(item: Pick<InventoryItem, "image_url">)'), true);
  const hosts = [...nextConfigSrc.matchAll(/hostname: "([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(hosts, ["cards.scryfall.io", "images.pokemontcg.io", "optcgapi.com", "placehold.co"]);
});

test("route gate unlocks staging only; intake and other routes stay locked", () => {
  assert.equal(gateCode.includes('"/admin/staging"'), false);
  for (const locked of ['"/admin/intake"', '"/admin/import"', '"/admin/settings"', '"/admin/shopify/sync"', '"/pos/pulls"', '"/pos/stats"']) {
    assert.equal(gateCode.includes(locked), true, `${locked} must stay locked`);
  }
});

test("dashboard and sidebar expose an honest Staging entry", () => {
  assert.equal(dashSrc.includes('href: "/admin/staging"'), true);
  assert.equal(dashSrc.includes("Staging Queue"), true);
  assert.equal(dashSrc.includes("Committing to inventory is not ready."), true);
  assert.equal(sidebarSrc.includes('{ href: "/admin/staging", label: "Staging", icon: Layers }'), true);
  assert.equal(sidebarSrc.includes('label: "Staging", icon: Layers, locked: true'), false);
});
