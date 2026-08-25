# slice-01-receive-foundation — implementation record

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.0.0 (frozen)  
**Unlock:** named human unlock, 2026-08-23 (after identity acceptance)  
**Status:** `IMPLEMENTED — AWAITING ACCEPTANCE DECISION`  
**Date:** 2026-08-23

## Files changed

New:

- `services/api/app/inventory_truth/__init__.py`
- `services/api/app/inventory_truth/models_truth.py` — frozen lot / event /
  cutover schema; NOT imported by `app.models`, `app.database`, `app.main`,
  or `worker`.
- `services/api/app/inventory_truth/migrator.py` — the approved migrator
  (`python -m app.inventory_truth.migrator`).
- `services/api/app/inventory_truth/core.py` — canonical keys, idempotent
  pair-write, cutover/freeze, reconciliation.
- `services/api/tests/test_inventory_truth.py` — 18 acceptance tests.
- `services/api/docs/…`: this file.

Modified:

- `services/api/app/logic/intake.py` — staging-commit dual-write hook
  (staging id captured before delete).
- `services/api/app/logic/trades.py` — trade-receive dual-write on both
  PurchaseRecord insert branches.
- `services/api/app/logic/sales.py` — POS finalize rejects while frozen
  (`ReceiveFrozenError`), per MIGRATION.md order step 3.
- `services/api/app/logic/sync_worker.py` — Shopify stock pull rejected
  while frozen (returns freeze message, no stock change).
- `services/api/app/routers/admin.py` — PATCH-stock freeze guard (503),
  plus `/inventory-truth/status`, `/inventory-truth/cutover`,
  `/inventory-truth/reconcile`.

## Schema and migration behaviour

1. Migrator creates additive unique indexes `(shop_id, id)` on live
   `inventory_item`, `purchase_record`, `sale` (indexes only).
2. Then tables `acquisition_lot` + `inventory_event`
   (`UNIQUE (shop_id, id)`, `UNIQUE (shop_id, idempotency_key)`,
   money `Numeric(12,2)`, `created_at` only) and
   `inventory_truth_cutover` (`UNIQUE (shop_id, generation)`).
3. Composite FKs all `ON DELETE RESTRICT`; event→lot required;
   item/purchase/sale/reverses nullable. Cross-shop pointers rejected by
   FK design (test asserts constraint presence).
4. Application `create_all` cannot create the three truth tables:
   acceptance test `test_app_create_all_does_not_create_truth_tables`.
5. Migrator is idempotent: re-run reports no new objects.

## Dual-write paths changed

- **Staging commit** (`commit_staging_item`): after snapshot update/WA and
  barcode, writes lot+event keyed
  `staging_commit:{shop_id}:{staging_item.id}` (id captured pre-delete).
- **Trade receive** (`apply_trade_values_to_staging`): each inserted
  PurchaseRecord gets lot+event keyed
  `purchase_record:{shop_id}:{purchase_record.id}` only (never also a
  staging key).
- Both hooks are gated on `cutover_status == complete`; pre-cutover shops
  keep exact pre-slice behavior (rollback drill test).

## Idempotency evidence

- Same string key on both rows in one transaction (`_write_pair`).
- both exist → no-op; lot w/o event → insert missing event same key;
  event w/o lot → `PermanentPairError` (failed_permanent, never skips);
  unique violation → savepoint rollback, treated as retry, no quantity
  added (concurrency-safe via nested transaction).
- Backfill A shares the live purchase_record key → rerun no-op
  (`test_duplicate_key_no_second_pair`, `test_cutover_backfills_purchases_and_gap`
  rerun assertion).

## Reconciliation results

`reconcile_shop` computes per-SKU `SUM(quantity_delta)` vs snapshot stock.
After cutover in tests: `unaccounted = 0` for backfill shop and
post-receive shop. Endpoint `/inventory-truth/reconcile` exposes it.

## Tests and results

`pytest tests/` → **104 passed** (70 prior identity/logic/notification +
20 slice tests + 14 PostgreSQL acceptance harness tests). Slice tests cover
migrator-only creation, additive indexes, unique keys, pair rules,
loss-not-Sale, freeze rejection (receive + PATCH stock + CSV import),
staging/trade dual-write, backfill A/B, rerun-no-op, recon zero, rollback
drill including the operator status-flip refreeze.

PostgreSQL acceptance evidence (14 owner criteria, disposable container,
synthetic data): `reviews/SLICE-01-PG-ACCEPTANCE.md`. Blocking CI job:
`.github/workflows/inventory-truth-gates.yml`.

## Rollback-drill result

PASS. The operator lever is the cutover row: flipping status back to
`locking` refreezes receives with no deploy; receives then reject cleanly
(no snapshot mutation, no truth rows). With dual-write off, staging commit
matches the pre-slice fixture exactly (stock +qty, WA cost unchanged
formula, one SyncOutbox stock_update, no Sale row). Truth tables may be
dropped; cutover row remains as evidence. No WA recompute from lots.

## Review findings

Recorded in `reviews/IMPLEMENTATION-CORRECTIONS.md`. Summary:

- P0s fixed: freeze now enforced on staging commit and trade receive
  (fail closed); CSV stock overwrite guarded; cutover locks item/purchase
  rows per contract order step 4.
- P1s fixed: savepoint-scoped duplicate handling; rebuilt event derived
  from stored lot; PATCH stock stays frozen until the adjust slice.
- P2s fixed: migrator creates truth tables only + post-apply
  verification; admin router lazy-imports truth core (migrator-only DDL
  letter intact); cutover endpoint owner-gated with generation pinned.
- One bounded verification pass after corrections: 90 tests passing.
- Residual follow-ups listed under blockers below.

## Remaining blockers

- **Implementation blockers:** none open.
- **Deployment gates:** identity membership unique index
  `(shop_id, clerk_user_id)` before any production schema apply
  (`docs/fail-closed-shop-identity-v1/ACCEPTANCE.md`). Inventory-truth
  schema apply itself requires human approval (no production migrations).
- **Specialist/go-live gates:** recon must be 0 at go-live; timeout is not
  green. Sell/Shopify dual-write is a later PR needing a new unlock.
  Direct stock overwrites (PATCH/CSV) remain frozen until the adjust
  slice.
- **Follow-ups:** Postgres CI leg to exercise `FOR UPDATE` locking
  semantics; ops runbook + audit logging for cutover invocations
  (DATABASE-CONTROLS §7 alignment); documented break-glass path if the
  cutover row lever is unavailable.

## Recommendation

**ACCEPT** the receive-foundation slice as matching the frozen contract
v1.0.0 wording, pending human review of this record.
