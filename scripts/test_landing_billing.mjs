import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pricingSrc = readFileSync(join(root, "components/custom-clerk-pricing.tsx"), "utf8");
const landingSrc = readFileSync(join(root, "app/(landing)/page.tsx"), "utf8");

test("billing defaults off and requires an explicit true flag", () => {
  assert.match(pricingSrc, /NEXT_PUBLIC_BILLING_ENABLED === "true"/);
  assert.equal(pricingSrc.includes("BILLING_ENABLED"), true);
});

test("disabled billing renders the accessible plans-coming-soon fallback", () => {
  assert.equal(pricingSrc.includes("Plans coming soon"), true);
  assert.equal(pricingSrc.includes('role="status"'), true);
  const fallbackIndex = pricingSrc.indexOf("Plans coming soon");
  const guardIndex = pricingSrc.indexOf("BILLING_ENABLED");
  assert.equal(fallbackIndex > -1, true);
  assert.equal(guardIndex > -1, true);
});

test("PricingTable renders only after the billing guard", () => {
  const guardIndex = pricingSrc.indexOf("if (!BILLING_ENABLED)");
  const tableIndex = pricingSrc.indexOf("<PricingTable");
  assert.equal(guardIndex > -1, true);
  assert.equal(tableIndex > -1, true);
  assert.equal(guardIndex < tableIndex, true);
});

test("landing page never embeds the raw Clerk PricingTable", () => {
  assert.equal(landingSrc.includes("PricingTable"), false);
});
