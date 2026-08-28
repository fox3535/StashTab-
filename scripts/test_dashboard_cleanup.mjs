import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardSrc = readFileSync(join(root, "app/admin/dashboard/page.tsx"), "utf8");
const gateSrc = readFileSync(join(root, "components/vendor/locked-route-gate.tsx"), "utf8");
const sidebarSrc = readFileSync(join(root, "components/product/product-sidebar.tsx"), "utf8");

test("dashboard uses membership shop context and never the env shop hint", () => {
  assert.equal(dashboardSrc.includes("useVendorShop"), true);
  assert.equal(dashboardSrc.includes("NEXT_PUBLIC_DEV_SHOP_ID"), false);
});

test("dashboard never invents metrics or fetches KPIs", () => {
  assert.equal(dashboardSrc.includes("adminRequest"), false);
  assert.equal(dashboardSrc.includes("total_revenue"), false);
  assert.equal(dashboardSrc.includes("inventory_value"), false);
  assert.equal(dashboardSrc.includes("never invents numbers"), true);
});

test("dashboard links the read-only tools and lists every deferred tool", () => {
  assert.equal(dashboardSrc.includes('"/admin/inventory"'), true);
  assert.equal(dashboardSrc.includes('"/pos/find"'), true);
  for (const label of ["Intake", "POS checkout", "Shopify", "Notifications", "Payments", "Watch"]) {
    assert.equal(dashboardSrc.includes(label), true, `missing deferred card ${label}`);
  }
  assert.equal(dashboardSrc.includes("Not ready"), true);
});

test("route gate unlocks dashboard but keeps shopify subroutes locked", () => {
  assert.equal(gateSrc.includes('"/admin/dashboard"'), false);
  assert.equal(gateSrc.includes('"/admin/shopify",'), false);
  assert.equal(gateSrc.includes('"/admin/shopify/sync"'), true);
  assert.equal(gateSrc.includes('"/admin/shopify/review"'), true);
  assert.equal(gateSrc.includes('"/admin/intake"'), true);
});

test("bare /admin/shopify renders an honest FeatureNotReady page", () => {
  const pagePath = join(root, "app/admin/shopify/page.tsx");
  assert.equal(existsSync(pagePath), true);
  const src = readFileSync(pagePath, "utf8");
  assert.equal(src.includes("FeatureNotReady"), true);
  assert.equal(src.includes("Shopify is not ready"), true);
});

test("sidebar dashboard entry is a live link, not locked", () => {
  assert.equal(sidebarSrc.includes('label: "Dashboard", icon: LayoutDashboard, locked'), false);
  assert.equal(sidebarSrc.includes('href: "/admin/dashboard"'), true);
});

test("dead env-shop-hint hook is removed", () => {
  assert.equal(existsSync(join(root, "lib/use-api-auth.ts")), false);
});
