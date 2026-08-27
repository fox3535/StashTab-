# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-27
**Branch:** `feature/prerequisite-my-shop-memberships-read-v1` from `main`
`09c1e6aba03f4a075159cdbdbddf61aa85157340`
**Staging API:** Railway deploy `17aeb85f-053f-4e5a-8d68-6d040d03c238` at Git SHA `0dd8f00b8d510b82e3d717a9570c0bc387e0479b`

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.1 and 1.1.2 frozen.
  Web Push off. Local 1.1.2 backend on `main` as `c3647a4`; not in production.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — frozen. Slices 01–03 on `main`
  via `c3647a4`. Staging schema applied 2026-08-27 (D-028). Not production.

## Current phase

`backend-foundation / staging-readiness-v1` (**PLAN.md F0**)
**F0 exit: PASSED FOR FRONTEND RECOVERY (D-035).** Not production approval.
**Slice-01 identity: COMPLETED, STAGING ONLY (D-025).**
**Slice-02 inventory schema: COMPLETED, APPLIED TO STAGING ONLY (D-028).**
**Slice-03 inventory read smoke: COMPLETED, STAGING ONLY (D-029).**
**Card-resolution intake/abstention: MERGED ON `main` `6a266b1` via PR #13
(D-034). FEATURE OFF. Not deployed. Not migrated on staging.**
Exact 13 staging tables. Inventory empty. API SELECT only; INSERT denied.
Writes, worker, Shopify, notifications, Watch remain off.

Production schema apply remains blocked. Convex is out (D-024).

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
   Staging/production schema and flags remain off.
6. F0 exit for frontend recovery: **passed** (D-035). F1 slice-01 is
   **approved** (D-036); implementation awaits a named unlock.
7. My-shop memberships read: **completed locally** (D-037). Not merged.
   Not deployed. Frontend slice-01 stays locked.
   Writes, notifications, Shopify, payments, Watch, workers, and Web Push
   stay disabled.

## Next queued phases

1. Frontend recovery: memberships-read prerequisite accepted locally
   (D-037), not merged; slice-01 shell + read-only inventory still awaits
   a named unlock after this prerequisite merges.
2. Later enablement, not F0: inventory write staging smoke, notification
   staging apply, production restore drill.
3. Do not enable card-resolution, writes, or push without a named unlock.
