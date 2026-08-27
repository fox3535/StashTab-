# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-27
**Branch:** `feature/card-resolution-intake-abstention-local-v0` (from `main` `d49eca9`; freeze checkpoint `671f663`)
**Staging API:** Railway deploy `17aeb85f-053f-4e5a-8d68-6d040d03c238` at Git SHA `0dd8f00b8d510b82e3d717a9570c0bc387e0479b`

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.1 and 1.1.2 frozen.
  Web Push off. Local 1.1.2 backend on `main` as `c3647a4`; not in production.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — frozen. Slices 01–03 on `main`
  via `c3647a4`. Staging schema applied 2026-08-27 (D-028). Not production.

## Current phase

`backend-foundation / staging-readiness-v1` (**PLAN.md F0**)
**Slice-01 identity: COMPLETED, STAGING ONLY (D-025).**
**Slice-02 inventory schema: COMPLETED, APPLIED TO STAGING ONLY (D-028).**
**Slice-03 inventory read smoke: COMPLETED, STAGING ONLY (D-029).**
**Card-resolution local intake/abstention: COMPLETED — NOT MERGED — NOT
DEPLOYED — FEATURE OFF (D-034).**
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
5. Local card-resolution intake/abstention: **accepted locally** (D-034).
   Not merged. Not deployed. Feature off. Staging/production remain off.
6. F1 frontend recovery blocked until the F0 exit gate.

## Next queued phases

1. Draft PR review for the local intake/abstention branch. Merge only after
   a separate owner instruction.
2. Later F0: inventory-truth staging proof (write unlock), notification
   staging mechanics, minimum security/ops.
3. F1 frontend recovery after the F0 exit gate.
