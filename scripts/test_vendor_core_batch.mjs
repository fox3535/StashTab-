// F1 vendor-core batch regression suite (Phase C).
//
// Covers the batch-level behaviours not already pinned by earlier suites:
// - test_protected_api_headers.mjs: bearer-only headers, no user header.
// - test_shop_session.mjs: zero/one/many memberships, stale preference,
//   shouldApplyShopResult, http kind mapping, fixture labeling.
// - test_pos_find_browse.mjs / test_admin_inventory_browse.mjs: totals,
//   offset pagination, exact SKU, stale-response rejection, error states.
//
// This suite adds: public vs protected routing, onboarding redirect/create
// states, duplicate-slug handling, sign-out clearing, dashboard honest
// cards, common error messages, deferred-feature honesty, accessible/mobile
// markup, and the negative checks (no Convex/Svix, no user-ID header, no
// dev-shop authority, no mock runtime inventory, no reachable billing
// widget inside vendor-core).
//
// Pure mirrors below stay in lockstep with lib/onboarding.ts and
// lib/vendor-api-error.ts; wiring assertions pin the pages to them.

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

const middlewareSrc = read("middleware.ts");
const onboardingLibSrc = read("lib/onboarding.ts");
const onboardingPageSrc = read("app/onboarding/page.tsx");
const dashboardSrc = read("app/admin/dashboard/page.tsx");
const inventorySrc = read("app/admin/inventory/page.tsx");
const findSrc = read("app/pos/find/page.tsx");
const patternsSrc = read("components/vendor/vendor-patterns.tsx");
const providerSrc = read("components/vendor/vendor-shop-provider.tsx");
const signOutSrc = read("components/vendor/sign-out-button.tsx");
const errorSrc = read("lib/vendor-api-error.ts");
const mimirSrc = read("lib/mimir-api.ts");
const adminLayoutSrc = read("app/admin/layout.tsx");

function collectVendorCore() {
  const dirs = [
    "app/onboarding",
    "app/admin/dashboard",
    "app/admin/inventory",
    "app/pos/find",
    "components/vendor",
  ];
  const files = [
    "app/admin/layout.tsx",
    "app/pos/layout.tsx",
    "lib/onboarding.ts",
    "lib/shop-session.ts",
    "lib/mimir-api.ts",
    "lib/vendor-api-error.ts",
    "lib/protected-api-headers.ts",
    "lib/pos-find.ts",
    "middleware.ts",
  ];
  let out = "";
  for (const dir of dirs) {
    for (const entry of readdirSync(join(root, dir), { recursive: true, withFileTypes: true })) {
      if (!entry.isFile()) continue;
      if (!/\.(ts|tsx|js|jsx|mjs)$/.test(entry.name)) continue;
      out += readFileSync(join(entry.parentPath ?? entry.path, entry.name), "utf8");
    }
  }
  for (const file of files) out += read(file);
  return out;
}
const vendorCoreSrc = collectVendorCore();

// --- pure mirrors (lockstep with lib/onboarding.ts) ---

function normalizeShopSlug(raw) {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function suggestSlug(name, slugEdited, currentSlug) {
  return slugEdited ? currentSlug : normalizeShopSlug(name);
}

function validateShopSetup(name, slug) {
  const trimmedName = name.trim();
  if (!trimmedName) return "Shop name is required.";
  if (trimmedName.length > 80) return "Shop name must be 80 characters or fewer.";
  const normalizedSlug = normalizeShopSlug(slug);
  if (!normalizedSlug) return "URL slug is required.";
  if (normalizedSlug.length > 80) return "URL slug must be 80 characters or fewer.";
  return null;
}

function decideOnboardingScreen(args) {
  if (!args.clerkLoaded) return "loading";
  if (!args.isSignedIn) return "session";
  if (args.membershipsLoading) return "loading";
  if (args.membershipsError) return "error";
  if (args.membershipCount > 0) return "enter";
  return "form";
}

function messageForCreateFailure(kind, message) {
  if (kind === "conflict") {
    return "That URL slug is already taken. Choose a different slug and try again.";
  }
  return message;
}

function messageForKind(kind, fallback) {
  switch (kind) {
    case "session_expired":
      return "Session expired. Sign in again.";
    case "forbidden":
      return "You do not have access to this shop.";
    case "conflict":
      return "Shop selection required.";
    case "not_ready":
      return "This feature is not ready.";
    case "not_found":
      return "No shop access.";
    case "network":
      return "Network error. Check your connection and try again.";
    default:
      return fallback || "Something went wrong. Try again.";
  }
}

// --- public versus protected routing ---

test("vendor surfaces are Clerk-protected; landing stays public", () => {
  assert.equal(middlewareSrc.includes('"/dashboard(.*)"'), true);
  assert.equal(middlewareSrc.includes('"/admin(.*)"'), true);
  assert.equal(middlewareSrc.includes('"/pos(.*)"'), true);
  assert.equal(middlewareSrc.includes('"/onboarding(.*)"'), true);
  assert.equal(middlewareSrc.includes("auth.protect()"), true);
  // The route matcher protects by named prefix; there is no blanket catch-all
  // that would gate the public landing page.
  assert.equal(middlewareSrc.includes('"/(.*)"'), false);
});

// --- onboarding redirect and create states ---

test("onboarding screen decision routes memberships correctly", () => {
  const base = { clerkLoaded: true, isSignedIn: true, membershipsError: "", membershipCount: 0 };
  assert.equal(decideOnboardingScreen({ ...base, clerkLoaded: false, membershipsLoading: false }), "loading");
  assert.equal(decideOnboardingScreen({ ...base, isSignedIn: false, membershipsLoading: false }), "session");
  assert.equal(decideOnboardingScreen({ ...base, membershipsLoading: true }), "loading");
  assert.equal(decideOnboardingScreen({ ...base, membershipsError: "down" }), "error");
  assert.equal(decideOnboardingScreen({ ...base, membershipCount: 1 }), "enter");
  assert.equal(decideOnboardingScreen({ ...base, membershipCount: 3 }), "enter");
  assert.equal(decideOnboardingScreen({ ...base, membershipsLoading: false }), "form");
});

test("onboarding page wires the accepted contracts and redirect", () => {
  assert.equal(onboardingPageSrc.includes("decideOnboardingScreen"), true);
  assert.equal(onboardingPageSrc.includes("mimirApi.listMyMemberships({ authToken: token })"), true);
  assert.equal(onboardingPageSrc.includes('router.replace("/admin/dashboard")'), true);
  assert.equal(onboardingPageSrc.includes("mimirApi.createShop(name.trim(), normalizedSlug, { authToken: token })"), true);
  assert.equal(onboardingPageSrc.includes("writeShopPreference(shop.id)"), true);
  // Double-submission guard.
  assert.equal(onboardingPageSrc.includes("if (inFlightRef.current || submitting) return;"), true);
  assert.equal(onboardingPageSrc.includes("disabled={submitting}"), true);
});

test("shop setup validation only allows API-supported fields", () => {
  assert.equal(validateShopSetup("", "my-shop"), "Shop name is required.");
  assert.equal(validateShopSetup("My Shop", "  "), "URL slug is required.");
  assert.equal(validateShopSetup("My Shop", "!!!"), "URL slug is required.");
  assert.equal(validateShopSetup("x".repeat(81), "ok"), "Shop name must be 80 characters or fewer.");
  assert.equal(validateShopSetup("ok", "x".repeat(81)), "URL slug must be 80 characters or fewer.");
  assert.equal(validateShopSetup("My Card Shop", "my-card-shop"), null);
  assert.equal(normalizeShopSlug("  My Card!! Shop  "), "my-card-shop");
  assert.equal(suggestSlug("My Card Shop", false, ""), "my-card-shop");
  assert.equal(suggestSlug("My Card Shop", true, "custom-slug"), "custom-slug");
  assert.equal(onboardingPageSrc.includes("validateShopSetup"), true);
  assert.equal(onboardingPageSrc.includes("suggestSlug"), true);
  // Submission must use the displayed (suggested) slug, not the raw state.
  assert.equal(onboardingPageSrc.includes("const effectiveSlug = suggestSlug(name, slugEdited, slug);"), true);
  assert.equal(onboardingPageSrc.includes("validateShopSetup(name, effectiveSlug)"), true);
  assert.equal(onboardingPageSrc.includes("normalizeShopSlug(effectiveSlug)"), true);
  // POST /shops body stays name + slug only.
  assert.equal(mimirSrc.includes('body: JSON.stringify({ name, slug })'), true);
});

// --- duplicate slug handling ---

test("duplicate slug 409 gets a fixable message", () => {
  assert.equal(
    messageForCreateFailure("conflict", "raw"),
    "That URL slug is already taken. Choose a different slug and try again."
  );
  assert.equal(messageForCreateFailure("network", "Network error. Check your connection and try again."), "Network error. Check your connection and try again.");
  assert.equal(onboardingPageSrc.includes("messageForCreateFailure(classified.kind, classified.message)"), true);
  assert.equal(onboardingPageSrc.includes("classifyVendorError"), true);
  assert.equal(onboardingLibSrc.includes('"conflict"'), true);
  assert.equal(errorSrc.includes("if (status === 409) return \"conflict\";"), true);
});

// --- sign-out and re-sign-in clearing ---

test("sign-out clears shop-sensitive state before leaving", () => {
  assert.equal(signOutSrc.includes("clearLocalSession();"), true);
  assert.equal(signOutSrc.includes('signOut({ redirectUrl: "/" })'), true);
  assert.equal(signOutSrc.indexOf("clearLocalSession();") < signOutSrc.indexOf("await signOut"), true);
  assert.equal(providerSrc.includes("clearShopPreference();"), true);
  assert.equal(providerSrc.includes('setPhase("session");'), true);
  assert.equal(providerSrc.includes("setSelectedShop(null);"), true);
  // Onboarding lives outside the provider and clears the preference itself.
  assert.equal(onboardingPageSrc.includes("clearShopPreference();"), true);
});

// --- dashboard honest cards ---

test("dashboard only links the accepted read-only tools", () => {
  assert.equal(dashboardSrc.includes('href: "/admin/inventory"'), true);
  assert.equal(dashboardSrc.includes('href: "/pos/find"'), true);
  assert.equal(dashboardSrc.includes('href: "/admin/sales"'), true);
  const hrefs = [...dashboardSrc.matchAll(/href: "([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(hrefs, ["/admin/inventory", "/admin/sales", "/pos/find"]);
  assert.equal(dashboardSrc.includes("Read-only"), true);
  assert.equal(dashboardSrc.includes("This page never invents numbers."), true);
});

test("deferred cards explain themselves and are not linked", () => {
  for (const label of ["Intake", "POS checkout", "Shopify", "Notifications", "Payments", "Watch"]) {
    assert.equal(dashboardSrc.includes(label), true);
  }
  assert.equal(dashboardSrc.includes("Not ready"), true);
  assert.equal(dashboardSrc.includes("No sale can be taken."), true);
  assert.equal(dashboardSrc.includes("No billing is active."), true);
  // Deferred cards render as plain list items, never links.
  assert.equal(dashboardSrc.includes("deferredCards.map(({ label, detail })"), true);
  assert.equal(/href: "(?!\/admin\/inventory|\/pos\/find|\/admin\/sales)/.test(dashboardSrc), false);
});

// --- all common error states ---

test("every common error kind has an honest vendor message", () => {
  assert.equal(messageForKind("session_expired", ""), "Session expired. Sign in again.");
  assert.equal(messageForKind("forbidden", ""), "You do not have access to this shop.");
  assert.equal(messageForKind("conflict", ""), "Shop selection required.");
  assert.equal(messageForKind("not_ready", ""), "This feature is not ready.");
  assert.equal(messageForKind("not_found", ""), "No shop access.");
  assert.equal(messageForKind("network", ""), "Network error. Check your connection and try again.");
  assert.equal(messageForKind("general", ""), "Something went wrong. Try again.");
  assert.equal(errorSrc.includes("messageForKind"), true);
  // Retry actions exist on the gate and onboarding error screens; the
  // browse pages show an honest error banner and re-run on the next search.
  assert.equal(providerSrc.includes("reload"), true);
  assert.equal(onboardingPageSrc.includes("Retry"), true);
  assert.equal(inventorySrc.includes("VendorErrorBanner"), true);
  assert.equal(findSrc.includes("VendorErrorBanner"), true);
});

// --- deferred-feature honesty on the accepted pages ---

test("locked features never appear operational", () => {
  assert.equal(onboardingPageSrc.includes("Shopify sync, payments, and notifications are deferred"), true);
  assert.equal(inventorySrc.includes("FeatureNotReady"), true);
  assert.equal(findSrc.includes("Selling is not ready") || dashboardSrc.includes("Selling is not ready."), true);
});

// --- mobile and keyboard-accessible markup ---

test("shared patterns expose live regions, labels, and reduced motion", () => {
  assert.equal(patternsSrc.includes('aria-label="Result pages"'), true);
  assert.equal(patternsSrc.includes('aria-label="Previous results page"'), true);
  assert.equal(patternsSrc.includes('aria-label="Next results page"'), true);
  assert.equal(patternsSrc.includes('role="status"'), true);
  assert.equal(patternsSrc.includes('role="alert"'), true);
  assert.equal(patternsSrc.includes("motion-reduce:animate-none"), true);
  assert.equal(patternsSrc.includes("min-h-11"), true);
});

test("vendor-core pages keep touch targets, focus rings, and no horizontal overflow", () => {
  for (const src of [onboardingPageSrc, inventorySrc, findSrc]) {
    assert.equal(/min-h-1[12]/.test(src), true);
  }
  for (const src of [onboardingPageSrc, dashboardSrc, inventorySrc, findSrc]) {
    assert.equal(src.includes("overflow-x-hidden"), true);
    assert.equal(src.includes("focus-visible"), true);
  }
  assert.equal(onboardingPageSrc.includes('htmlFor="shop-name"'), true);
  assert.equal(onboardingPageSrc.includes('htmlFor="shop-slug"'), true);
  assert.equal(onboardingPageSrc.includes('aria-live="polite"'), true);
  assert.equal(onboardingPageSrc.includes('aria-describedby="shop-setup-help"'), true);
});

// --- negative checks ---

test("vendor-core has no Convex, Svix, or user-ID header authority", () => {
  const lowered = vendorCoreSrc.toLowerCase();
  assert.equal(lowered.includes("convex"), false);
  assert.equal(lowered.includes("svix"), false);
  assert.equal(vendorCoreSrc.includes("X-Clerk-User-Id"), false);
  assert.equal(vendorCoreSrc.includes("clerk_user_id"), false);
});

test("no dev-shop fallback authority inside vendor-core", () => {
  assert.equal(vendorCoreSrc.includes("NEXT_PUBLIC_DEV_SHOP_ID"), false);
});

test("no fixture data can appear in runtime vendor-core code", () => {
  assert.equal(vendorCoreSrc.includes("LOCAL_TEST_FIXTURE"), false);
  assert.equal(vendorCoreSrc.includes("FIX-1"), false);
  assert.equal(vendorCoreSrc.includes("Fixture Charizard"), false);
});

test("billing widget is not reachable from vendor-core pages", () => {
  for (const src of [onboardingPageSrc, dashboardSrc, inventorySrc, findSrc, adminLayoutSrc, providerSrc]) {
    assert.equal(src.includes("custom-clerk-pricing"), false);
    assert.equal(src.includes("CustomClerkPricing"), false);
  }
  // The widget stays confined to the landing page and the billing gate.
  assert.equal(read("components/admin-billing-gate.tsx").includes("CustomClerkPricing"), true);
});
