import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const footerSrc = readFileSync(join(root, "app/(landing)/footer.tsx"), "utf8");
const headerSrc = readFileSync(join(root, "app/(landing)/header.tsx"), "utf8");
const paymentGatedSrc = readFileSync(join(root, "app/dashboard/payment-gated/page.tsx"), "utf8");
const dashboardSrc = readFileSync(join(root, "app/dashboard/page.tsx"), "utf8");
const middlewareSrc = readFileSync(join(root, "middleware.ts"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");

test("landing footer uses explicit Open POS Find with matching target", () => {
  assert.equal(footerSrc.includes("Open POS Find"), true);
  assert.equal(footerSrc.includes("'/pos/find'"), true);
  assert.equal(footerSrc.includes("'/pos'"), false);
});

test("landing surfaces never link the locked bare /pos route", () => {
  assert.equal(footerSrc.includes('href="/pos"'), false);
  assert.equal(headerSrc.includes('href="/pos"'), false);
  assert.equal(headerSrc.includes("Open POS Find"), true);
});

test("payment-gated starter route never implies billing works", () => {
  assert.equal(paymentGatedSrc.includes('redirect("/admin/dashboard")'), true);
  assert.equal(paymentGatedSrc.includes("CustomClerkPricing"), false);
  assert.equal(paymentGatedSrc.includes("Upgrade to a paid plan"), false);
  assert.equal(paymentGatedSrc.includes("Protect"), false);
});

test("retired /dashboard starter routes redirect to the vendor dashboard", () => {
  assert.equal(dashboardSrc.includes('redirect("/admin/dashboard")'), true);
});

test("Clerk protection stays intact for corrected routes", () => {
  assert.equal(middlewareSrc.includes('"/dashboard(.*)"'), true);
  assert.equal(middlewareSrc.includes('"/pos(.*)"'), true);
  assert.equal(middlewareSrc.includes("auth.protect()"), true);
});

test("bare /pos stays locked; links were corrected, not routes unlocked", () => {
  assert.equal(gateSrc.includes('"/pos"'), true);
});
