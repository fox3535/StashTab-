import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(join(root, "lib/protected-api-headers.ts"), "utf8");

class SessionExpiredError extends Error {
  constructor(message = "Session expired. Sign in again.") {
    super(message);
    this.name = "SessionExpiredError";
  }
}

function buildProtectedApiHeaders(auth) {
  const token = typeof auth.authToken === "string" ? auth.authToken.trim() : "";
  if (!token) throw new SessionExpiredError();
  const headers = { Authorization: `Bearer ${token}` };
  if (auth.shopId) headers["X-Shop-Id"] = auth.shopId;
  return headers;
}

test("source never sends caller user identity headers", () => {
  assert.equal(source.includes("X-Clerk-User-Id"), false);
  assert.equal(source.includes("Authorization"), true);
});

test("protected calls include the Clerk bearer token", () => {
  const headers = buildProtectedApiHeaders({
    authToken: "clerk-session-token",
    shopId: "shop-a",
  });
  assert.equal(headers.Authorization, "Bearer clerk-session-token");
  assert.equal(headers["X-Shop-Id"], "shop-a");
  assert.equal("X-Clerk-User-Id" in headers, false);
});

test("missing token does not fall back to shop or user headers", () => {
  assert.throws(() => buildProtectedApiHeaders({ shopId: "shop-a" }), SessionExpiredError);
  assert.throws(
    () => buildProtectedApiHeaders({ authToken: "  ", shopId: "shop-a" }),
    SessionExpiredError
  );
});

test("shop id is only an untrusted hint", () => {
  const headers = buildProtectedApiHeaders({ authToken: "tok" });
  assert.equal("X-Shop-Id" in headers, false);
  assert.equal(headers.Authorization, "Bearer tok");
});
