import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const adminSrc = readFileSync(join(root, "app/admin/page.tsx"), "utf8");
const dashboardSrc = readFileSync(join(root, "app/dashboard/page.tsx"), "utf8");
const onboardingSrc = readFileSync(join(root, "app/onboarding/page.tsx"), "utf8");
const middlewareSrc = readFileSync(join(root, "middleware.ts"), "utf8");
const landingSrc = readFileSync(join(root, "app/(landing)/page.tsx"), "utf8");
const landingHeaderSrc = readFileSync(join(root, "app/(landing)/header.tsx"), "utf8");

test("/admin redirects to the sole vendor dashboard", () => {
  assert.equal(adminSrc.includes('redirect("/admin/dashboard")'), true);
  assert.equal(adminSrc.includes("adminLinks"), false);
  assert.equal(adminSrc.includes("KPIs"), false);
});

test("protected /dashboard redirects to the sole vendor dashboard", () => {
  assert.equal(dashboardSrc.includes('redirect("/admin/dashboard")'), true);
  assert.equal(dashboardSrc.includes("DataTable"), false);
  assert.equal(dashboardSrc.includes("SectionCards"), false);
});

test("Clerk protection and redirect intent are preserved", () => {
  for (const route of ['"/dashboard(.*)"', '"/admin(.*)"', '"/pos(.*)"', '"/onboarding(.*)"']) {
    assert.equal(middlewareSrc.includes(route), true, `middleware lost ${route}`);
  }
  assert.equal(middlewareSrc.includes("auth.protect()"), true);
});

test("onboarding success and skip enter the vendor dashboard, never locked /pos", () => {
  assert.equal(onboardingSrc.includes('router.push("/admin/dashboard")'), true);
  assert.equal(onboardingSrc.includes('router.push("/pos")'), false);
  assert.equal(onboardingSrc.includes("Finish & open dashboard"), true);
});

test("public landing stays public and its signed-in CTA avoids locked /pos", () => {
  assert.equal(existsSync(join(root, "app/(landing)/page.tsx")), true);
  assert.equal(landingSrc.includes("redirect("), false);
  assert.equal(landingHeaderSrc.includes('href="/pos"'), false);
  assert.equal(landingHeaderSrc.includes('href="/pos/find"'), true);
});

test("signed-in landing CTAs pair explicit labels with matching targets", () => {
  // A general entry action must go to /admin/dashboard; /pos/find is only
  // allowed behind an explicit POS Find label.
  assert.equal(landingHeaderSrc.includes("Open POS Find"), true);
  assert.equal(landingHeaderSrc.includes('href="/admin/dashboard"'), true);
  assert.equal(landingHeaderSrc.includes("Get Started"), false);
  assert.equal(landingHeaderSrc.includes("Open App"), false);
});
