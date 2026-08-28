# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-28
**Branch:** `main` at `aaac4e4` (slice-06 PR #23 merged); `feature/f1-vendor-core-recovery-batch` in draft review
**Staging API:** Railway deploy `9c47945a` of `main` (staging smoke passed, D-039)

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.1 and 1.1.2 frozen.
  Web Push off. Local 1.1.2 backend on `main` as `c3647a4`; not in production.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — frozen. Slices 01–03 on `main`
  via `c3647a4`. Staging schema applied 2026-08-27 (D-028). Not production.

## Current phase

`frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`
**Status:** `ACCEPTED — MERGED ON main — STAGING SMOKE PASSED — FRONTEND NOT DEPLOYED` (D-038, D-039).
F0 exit remains passed for frontend recovery (D-035). Memberships read is
hosted on staging via deploy `9c47945a`. Frontend was smoke-tested locally
at `http://localhost:3001`, never deployed.

Writes, worker, Shopify, notifications, Watch remain off. Convex is out (D-024).

## Approved boundaries

- Python/FastAPI owns business logic; tenant data uses `shop_id`.
- Identity: signed token + membership. Shop header is an untrusted hint.
- Partner Python is `vendor/mimir-partner/`; inspect, do not copy blindly.
- Humans approve writes, Web Push, payments, Watch, and later slices.

## Active gates

1. Identity smoke: **closed** (D-025).
2. Inventory schema on staging: **closed** (D-028).
3. Inventory read smoke: **closed** (D-029). Writes still off.
4. Production schema apply blocked.
5. Card-resolution intake/abstention: **merged, feature off** (D-034 / PR #13).
6. F0 exit for frontend recovery: **passed** (D-035).
7. My-shop memberships read: **merged on `main` via PR #15** (D-037), hosted on staging via deploy `9c47945a`.
8. F1 slice-01 shell + read inventory: **accepted** (D-038 local, D-039 live smoke).
   Merged on `main` `3c3ca33`; staging smoke passed: real Clerk memberships,
   live staging inventory read, full keyboard walkthrough, mobile, sign-out
   and re-sign-in. No schema or data writes.

## Next queued phases

1. Owner review of the F1 vendor-core batch draft PR
   (`F1-VENDOR-CORE-BATCH-PRESERVATION.md`): onboarding recovery,
   vendor-core pattern consolidation, regression suite. Not merged,
   not deployed.
2. Frontend recovery continuation: next slice planning per
   `docs/frontend-recovery-v1/`; navigation/deferred-routes cleanup item for
   bare `/admin/shopify` 404 (non-blocking UX backlog).
3. Later enablement, not F0: inventory write staging smoke, notification
   staging apply, production restore drill.
4. Do not enable card-resolution, writes, or push without a named unlock.
