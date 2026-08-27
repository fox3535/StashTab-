# Slice-01 authenticated shell and read-only inventory — local acceptance

**Slice:** `frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`  
**Status:** `COMPLETED LOCALLY — NOT MERGED — NOT DEPLOYED — LIVE STAGING SMOKE PENDING`  
**Decision:** D-038  
**Accepted:** named human owner 2026-08-27  
**Pinned `main`:** `af72bac501cd9c42b70cd0347f778db388c8c943`  
**Branch:** `feature/slice-01-authenticated-shell-read-inventory`  
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

## Later staging-smoke gates (not local blockers)

- Real Clerk membership loading against staging
- Live staging inventory read
- Full keyboard walkthrough of the authenticated shell

## Explicitly not accepted

Merge to `main`, deploy, migrate, write enablement, Shopify, notifications, payments, Watch, or a live staging smoke.
