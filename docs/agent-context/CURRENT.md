# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-27
**Branch:** `main` `d49eca9fc31298847bd07abf42347ab691b4f974`
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
Exact 13 tables. Inventory empty. API SELECT only; INSERT denied.
Worker/readonly grants from D-028. Search 200 empty / cross-shop 403.
CSV quantity 503. PATCH/checkout/intake write guards not fully proven.
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
5. `card-resolution-core-v1` implementation blocked. Intake/abstention
   planning D-030; snapshot D-031; scoring **D-033 frozen** as
   `identity-score-v0` under contract 1.0.0 §16. No amendment.
6. F1 frontend recovery blocked until the F0 exit gate.

## Next queued phases

1. Named **implementation unlock** for local intake/abstention
   (`DIRECTIVE-SLICE-01-LOCAL-IMPLEMENTATION.md`, not authorized).
2. Later F0: inventory-truth staging proof (write unlock), notification
   staging mechanics, minimum security/ops.
3. F1 frontend recovery after the F0 exit gate.
