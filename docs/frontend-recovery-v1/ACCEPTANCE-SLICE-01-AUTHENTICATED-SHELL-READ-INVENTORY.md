# Slice-01 authenticated shell and read-only inventory — acceptance

**Slice:** `frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`  
**Status:** `ACCEPTED — MERGED ON main — STAGING SMOKE PASSED — FRONTEND NOT DEPLOYED`  
**Decision:** D-038 (local acceptance), D-039 (final acceptance)  
**Accepted:** named human owner 2026-08-27 (local); named human owner 2026-08-27 (live smoke)  
**Frontend on `main`:** `3c3ca33` (slice-01 merged via PR #16, landing billing fix via PR #17)  
**Staging API deploy:** Railway `9c47945a`  
**This file is not in freeze hashes.** Frozen contracts were not rewritten.

## Accepted locally

- Shop authority is `GET /api/v1/shops/me/memberships` with a Clerk bearer token.
- No `X-Clerk-User-Id` header.
- `X-Shop-Id` is a selected-membership hint only.
- Local stored shop ID is preference only and cannot grant access.
- Stale, malformed, or unauthorized preferences are discarded.
- Shop switching clears prior inventory and ignores late responses from the previous shop.
- Sign-out clears shop preference and sensitive UI state.
- Zero memberships cannot reach inventory.
- Inventory search is read-only.
- Deferred tools are visibly not ready, including on direct URLs, and remain Clerk-protected.
- Public landing stays public.
- No Convex/Svix, no backend/API-contract change, no secrets.

The visual harness is `scripts/slice-01-visual-harness.html`. It is not a Next.js route and is not a production product screen. `LOCAL_TEST_FIXTURE` data exists only in tests/harness files.

## Live staging smoke — passed 2026-08-27 (D-039)

Recorded facts:

- Frontend code merged on `main` `3c3ca33`.
- Staging API deploy `9c47945a`.
- Frontend tested locally at `http://localhost:3001`, not deployed.
- Real Clerk membership loaded.
- Smoke Shop B auto-selected.
- Read-only inventory returned an honest empty state.
- Sign-out and re-sign-in passed.
- Keyboard and mobile checks passed.
- Deferred features remained locked.
- No schema or data writes occurred.

Non-blocking UX backlog item: bare `/admin/shopify` renders a 404 instead of
a Not Ready screen. No visible navigation links to that bare route (links
target locked subroutes), so it is not a slice-01 blocker. It becomes an
honest Not Ready route in a later navigation/deferred-routes cleanup.

## Explicitly not accepted

Frontend deploy, migrate, write enablement, Shopify, notifications,
payments, Watch, or any production approval.
