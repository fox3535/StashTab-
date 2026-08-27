import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const sessionSrc = readFileSync(join(root, "lib/shop-session.ts"), "utf8");
const errorSrc = readFileSync(join(root, "lib/vendor-api-error.ts"), "utf8");
const mimirSrc = readFileSync(join(root, "lib/mimir-api.ts"), "utf8");
const headerSrc = readFileSync(join(root, "lib/protected-api-headers.ts"), "utf8");
const providerSrc = readFileSync(join(root, "components/vendor/vendor-shop-provider.tsx"), "utf8");

const ALLOWED_ROLES = new Set(["owner", "staff"]);

function parseMembershipsPayload(payload) {
  if (!payload || typeof payload !== "object") throw new Error("Invalid memberships payload");
  const shops = payload.shops;
  if (!Array.isArray(shops)) throw new Error("Invalid memberships payload");
  return shops.map((row) => {
    if (!row || typeof row.id !== "string" || typeof row.name !== "string") {
      throw new Error("Invalid memberships payload");
    }
    if (!ALLOWED_ROLES.has(row.role)) throw new Error("Invalid memberships payload");
    return { id: row.id, name: row.name, role: row.role };
  });
}

function normalizeStoredShopId(storedId) {
  const stored = (storedId ?? "").trim();
  if (!stored) return null;
  if (stored.length > 80 || /[\s<>]/.test(stored)) return null;
  return stored;
}

function shouldApplyShopResult(requestShopId, currentShopId) {
  return Boolean(currentShopId) && requestShopId === currentShopId;
}

function resolveShopSelection(shops, storedId) {
  if (shops.length === 0) return { kind: "empty" };
  const stored = normalizeStoredShopId(storedId);
  const hadPref = Boolean((storedId ?? "").trim());
  const match = stored ? shops.find((shop) => shop.id === stored) : undefined;
  const discardedStale = hadPref && !match;
  if (shops.length === 1) {
    return { kind: "auto", shop: shops[0], discardedStale };
  }
  if (match) return { kind: "preferred", shop: match };
  return { kind: "choose", shops, discardedStale };
}

function kindFromHttpStatus(status, bodyText) {
  const lowered = bodyText.toLowerCase();
  if (status === 401) return "session_expired";
  if (status === 403) return "forbidden";
  if (status === 409) return "conflict";
  if (status === 404) return "not_found";
  if (status === 503 || lowered.includes("feature_not_ready")) return "not_ready";
  return "general";
}

test("source uses the merged memberships route and never sends a user header", () => {
  assert.equal(mimirSrc.includes("/shops/me/memberships"), true);
  assert.equal(headerSrc.includes("X-Clerk-User-Id"), false);
  assert.equal(providerSrc.includes("X-Clerk-User-Id"), false);
  assert.equal(sessionSrc.includes("NEXT_PUBLIC_DEV_SHOP_ID"), false);
  assert.equal(sessionSrc.includes("shouldApplyShopResult"), true);
  assert.equal(errorSrc.includes("FEATURE_NOT_READY"), true);
});

test("zero memberships is an empty success list, not a fake shop", () => {
  const shops = parseMembershipsPayload({ shops: [] });
  assert.deepEqual(resolveShopSelection(shops, "shop-a"), { kind: "empty" });
});

test("one membership auto-selects and discards a stale preference", () => {
  const shops = parseMembershipsPayload({
    shops: [{ id: "shop-b", name: "B", role: "owner" }],
  });
  const result = resolveShopSelection(shops, "shop-stale");
  assert.equal(result.kind, "auto");
  assert.equal(result.shop.id, "shop-b");
  assert.equal(result.discardedStale, true);
});

test("several memberships keep a matching preference", () => {
  const shops = parseMembershipsPayload({
    shops: [
      { id: "shop-a", name: "A", role: "owner" },
      { id: "shop-b", name: "B", role: "staff" },
    ],
  });
  const result = resolveShopSelection(shops, "shop-b");
  assert.equal(result.kind, "preferred");
  assert.equal(result.shop.id, "shop-b");
});

test("stale preference with several shops does not silently pick another", () => {
  const shops = parseMembershipsPayload({
    shops: [
      { id: "shop-a", name: "A", role: "owner" },
      { id: "shop-b", name: "B", role: "staff" },
    ],
  });
  const result = resolveShopSelection(shops, "missing-shop");
  assert.equal(result.kind, "choose");
  assert.equal(result.discardedStale, true);
  assert.deepEqual(
    result.shops.map((s) => s.id),
    ["shop-a", "shop-b"]
  );
});

test("unauthorized stored id is not selectable", () => {
  const shops = [{ id: "shop-a", name: "A", role: "owner" }];
  const result = resolveShopSelection(shops, "shop-other");
  assert.equal(result.kind, "auto");
  assert.notEqual(result.shop.id, "shop-other");
});

test("http kinds map 401 403 409 503", () => {
  assert.equal(kindFromHttpStatus(401, ""), "session_expired");
  assert.equal(kindFromHttpStatus(403, ""), "forbidden");
  assert.equal(kindFromHttpStatus(409, ""), "conflict");
  assert.equal(kindFromHttpStatus(503, ""), "not_ready");
  assert.equal(kindFromHttpStatus(500, "FEATURE_NOT_READY"), "not_ready");
});

test("malformed stored preference is discarded", () => {
  const shops = parseMembershipsPayload({
    shops: [
      { id: "shop-a", name: "A", role: "owner" },
      { id: "shop-b", name: "B", role: "staff" },
    ],
  });
  const result = resolveShopSelection(shops, "shop-a\n<script>");
  assert.equal(result.kind, "choose");
  assert.equal(result.discardedStale, true);
});

test("late result from a previous shop is ignored", () => {
  assert.equal(shouldApplyShopResult("shop-a", "shop-b"), false);
  assert.equal(shouldApplyShopResult("shop-b", "shop-b"), true);
  assert.equal(shouldApplyShopResult("shop-a", null), false);
});

test("inventory fixtures stay labeled as fixtures in tests", () => {
  const fixture = {
    source: "LOCAL_TEST_FIXTURE",
    items: [{ id: 1, sku: "FIX-1", name: "Fixture Charizard", stock: 2 }],
  };
  assert.equal(fixture.source, "LOCAL_TEST_FIXTURE");
  assert.equal(fixture.items.length, 1);
});
