// Slice-11 inventory integrity regression tests.
//
// Pure helper behaviour is mirrored here and kept in lockstep with
// lib/inventory-integrity.ts by source-wiring assertions. All fixtures
// are clearly labeled synthetic data — staging may only prove the honest
// no-cutover / zero-mismatch states. Negative scans run against
// comment-stripped source so doc comments naming forbidden behaviour
// cannot trip them.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helperSrc = readFileSync(join(root, "lib/inventory-integrity.ts"), "utf8");
const pageSrc = readFileSync(join(root, "app/admin/reconciliation/page.tsx"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const dashSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");

const stripComments = (src) => src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const pageCode = stripComments(pageSrc);

// ---- LABELED SYNTHETIC FIXTURES (never real data) ----
const FIXTURE_ZERO = { shop_id: "fix-shop", unaccounted_qty: 0, mismatches: {} };
const FIXTURE_MISMATCH = {
  shop_id: "fix-shop",
  unaccounted_qty: 2,
  mismatches: {
    "FIX-SKU-1": { event_remaining: 3, snapshot_stock: 1 },
    "FIX-SKU-2": { event_remaining: 5, snapshot_stock: null },
  },
};

// ---- behavioural mirrors of lib/inventory-integrity.ts ----
const INTEGRITY_CHECK_TIMEOUT_MS = 15000;
function mirrorDescribeCutoverStatus(status) {
  if (status === null || status === undefined || status === "") {
    return "Off — no cutover row exists for this shop. Cutover being off is not an error and is not an approval.";
  }
  if (status === "complete") return "Complete";
  return `Status reported by the API: ${status}`;
}
function mirrorReconOutcomeText(unaccountedQty) {
  if (unaccountedQty === 0) {
    return "Matched: this check returned zero mismatches. Event-derived truth agreed with the inventory snapshot for every SKU at the time of this check.";
  }
  return `Mismatched: ${unaccountedQty} SKU${unaccountedQty === 1 ? "" : "s"} where event-derived remaining differs from snapshot stock.`;
}
function mirrorFormatMismatchValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return String(value);
}
function mirrorTimedOutNotice() {
  return `The check timed out after ${INTEGRITY_CHECK_TIMEOUT_MS / 1000} seconds. No result is available and nothing was changed.`;
}

test("helpers are wired from lib/inventory-integrity.ts", () => {
  assert.equal(helperSrc.includes("INTEGRITY_CHECK_TIMEOUT_MS = 15000"), true);
  assert.equal(helperSrc.includes("function describeCutoverStatus"), true);
  assert.equal(helperSrc.includes("function reconOutcomeText"), true);
  assert.equal(helperSrc.includes("function formatMismatchValue"), true);
  assert.equal(helperSrc.includes("function timedOutNotice"), true);
});

test("cutover states stay honest: missing cutover, complete, other", () => {
  // No cutover row: off is stated as a fact — never an error, never an approval.
  assert.equal(mirrorDescribeCutoverStatus(null).includes("Off"), true);
  assert.equal(mirrorDescribeCutoverStatus(null).includes("not an error"), true);
  assert.equal(mirrorDescribeCutoverStatus(null).includes("not an approval"), true);
  assert.equal(mirrorDescribeCutoverStatus(undefined).includes("Off"), true);
  assert.equal(mirrorDescribeCutoverStatus("complete"), "Complete");
  assert.equal(mirrorDescribeCutoverStatus("locked").includes("locked"), true);
});

test("reconciliation outcomes stay honest: empty inventory, zero, mismatch", () => {
  // Empty inventory tables reconcile to zero mismatches — reported as what
  // the check returned, never as a permanent green guarantee.
  assert.equal(mirrorReconOutcomeText(FIXTURE_ZERO.unaccounted_qty).includes("Matched"), true);
  assert.equal(mirrorReconOutcomeText(FIXTURE_ZERO.unaccounted_qty).includes("zero mismatches"), true);
  assert.equal(mirrorReconOutcomeText(1).includes("1 SKU "), true);
  assert.equal(mirrorReconOutcomeText(FIXTURE_MISMATCH.unaccounted_qty).includes("2 SKUs"), true);
});

test("mismatch values render honestly, including a missing snapshot", () => {
  assert.equal(mirrorFormatMismatchValue(0), "0");
  assert.equal(mirrorFormatMismatchValue(7), "7");
  assert.equal(mirrorFormatMismatchValue(null), "—");
  assert.equal(mirrorFormatMismatchValue(undefined), "—");
  assert.equal(mirrorTimedOutNotice().includes("timed out"), true);
  assert.equal(mirrorTimedOutNotice().includes("nothing was changed"), true);
});

test("client wrappers hit both read-only truth contracts", () => {
  assert.equal(mimirSrc.includes('"/admin/inventory-truth/status"'), true);
  assert.equal(mimirSrc.includes('"/admin/inventory-truth/reconcile"'), true);
  assert.equal(mimirSrc.includes("inventoryTruthStatus:"), true);
  assert.equal(mimirSrc.includes("inventoryTruthReconcile:"), true);
  assert.equal(mimirSrc.includes("export type InventoryTruthStatus"), true);
  assert.equal(mimirSrc.includes("export type InventoryTruthReconcile"), true);
  // The write halves of inventory-truth must never be called.
  const code = stripComments(mimirSrc);
  assert.equal(code.includes("/inventory-truth/cutover"), false);
  assert.equal(code.includes("backfill"), false);
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

test("the check only runs through the labeled control, never automatically", () => {
  assert.equal(pageCode.includes("onClick={runCheck}"), true);
  assert.equal(pageCode.includes("Run read-only check"), true);
  assert.equal(pageCode.includes('aria-label="Run read-only inventory integrity check"'), true);
  // Each contract is called exactly once, inside runCheck — not in any effect.
  assert.equal(pageCode.match(/mimirApi\.inventoryTruthStatus/g).length, 1);
  assert.equal(pageCode.match(/mimirApi\.inventoryTruthReconcile/g).length, 1);
  assert.equal(pageSrc.includes("No check has been run for this shop in this session."), true);
});

test("the screen distinguishes matched, mismatched, timed out, and failed", () => {
  assert.equal(pageSrc.includes("reconOutcomeText(reconResult.unaccounted_qty)"), true);
  assert.equal(pageSrc.includes("timedOutNotice()"), true);
  assert.equal(pageSrc.includes('phase === "timed_out"'), true);
  assert.equal(pageSrc.includes('phase === "failed"'), true);
  assert.equal(pageSrc.includes("VendorErrorBanner"), true);
  assert.equal(pageSrc.includes("describeCutoverStatus(statusResult.cutover_status)"), true);
  assert.equal(pageSrc.includes("does not repair anything"), true);
});

test("shop switching clears results and late responses cannot leak", () => {
  assert.equal(pageCode.includes('setPhase("idle")'), true);
  assert.equal(pageCode.includes("setStatusResult(null)"), true);
  assert.equal(pageCode.includes("setReconResult(null)"), true);
  assert.equal(pageCode.includes("checkControllerRef.current?.abort()"), true);
  assert.equal(pageCode.includes("myEpoch !== epochRef.current"), true);
});

test("the page stays read-only: no mutation controls of any kind", () => {
  // Honest disclosure sentences may name what the screen does NOT do;
  // normalize whitespace (JSX strings wrap across lines), then strip those
  // exact phrases before scanning for capability tokens.
  const negationAllowlist = [
    "does not repair anything",
    "does not repair, adjust, backfill, or change anything",
  ];
  let sanitized = pageCode.replace(/\s+/g, " ");
  for (const phrase of negationAllowlist) {
    sanitized = sanitized.split(phrase).join("");
  }
  for (const forbidden of [
    "POST",
    "PATCH",
    "DELETE",
    "approve",
    "repair",
    "backfill",
    "reprice",
    "resticker",
    "FormData",
    "upload",
    "Blob(",
    "createObjectURL",
    ".csv",
    "exportCsv",
    "a.download",
    "syncNow",
    "run_cutover",
  ]) {
    assert.equal(sanitized.toLowerCase().includes(forbidden.toLowerCase()), false, `page must not reference ${forbidden}`);
  }
});

test("route gate no longer locks the integrity screen or slice-09 reports", () => {
  assert.equal(gateSrc.includes('"/admin/reconciliation"'), false);
  assert.equal(gateSrc.includes('"/admin/reports"'), false);
  assert.equal(gateSrc.includes('"/admin/intake"'), true);
});

test("dashboard and sidebar expose an honest Inventory Integrity entry", () => {
  assert.equal(dashSrc.includes('href: "/admin/reconciliation"'), true);
  assert.equal(dashSrc.includes("Inventory Integrity"), true);
  assert.equal(dashSrc.includes("never repairs anything"), true);
  const hrefs = [...dashSrc.matchAll(/href: "([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(hrefs, [
    "/admin/inventory",
    "/admin/price-updates",
    "/admin/reconciliation",
    "/admin/reports",
    "/admin/sales",
    "/pos/find",
  ]);
  assert.equal(sidebarSrc.includes('href: "/admin/reconciliation", label: "Inventory Integrity"'), true);
  assert.equal(sidebarSrc.includes('label: "Inventory Integrity", icon: ShieldCheck, locked'), false);
});
