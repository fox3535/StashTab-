# slice-01-receive-foundation — PostgreSQL acceptance evidence

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.0.0 (frozen)
**Scope:** bounded PostgreSQL acceptance pass, per owner instruction 2026-08-23
**Harness:** `services/api/tests/test_pg_acceptance.py` (skipped unless
`STASHTAB_PG_URL` is set; normal SQLite suite unaffected)
**Database:** disposable local Docker `postgres:16-alpine`, synthetic data only;
destroyed after the run. No production credentials, no production access.

## Environment

| Item | Value |
| --- | --- |
| Image | `postgres:16-alpine` (fresh container each pass) |
| URL shape | `postgresql+psycopg2://postgres:stashtab@localhost:55432/stashtab_it` |
| Driver | `psycopg2-binary>=2.9.10` (already in requirements.txt) |
| Schema source | app `create_all` for pre-slice schema; approved migrator for truth DDL |

## Criteria results — first pass

Corrections applied before this pass (clear slice-local defects from review):

1. `ck_overlay_zero_delta` rewritten as a boolean predicate
   (`NOT (overlay type) OR quantity_delta = 0`). The previous portable-CASE
   wording mixed integer and boolean branches and was rejected by PostgreSQL.
2. Migrator made atomic: indexes + tables now apply in ONE transaction with a
   `fail_after` test hook; mid-point failure rolls back completely.
3. `register_composite_fks()` made re-call-safe; previously a second call in
   one process appended duplicate FK constraints and emitted invalid duplicate
   DDL on PostgreSQL.
4. POS route maps `ReceiveFrozenError` to HTTP 503 (was an unhandled 500).
5. Trade apply loop re-raises freeze/failed-permanent instead of counting
   them as per-item errors while earlier items stay staged.

First full-pass result after those corrections: **14 / 14 PASS**
(34.7 s). One harness-only fix followed (test 10 orphan shape rebuilt to be
expressible under real FK enforcement), then all runs green.

## Criteria mapping and evidence (final run)

| # | Criterion | Result | Evidence (test) |
| --- | --- | --- | --- |
| 1 | Migrator succeeds from pre-inventory schema | PASS | `TestMigrator::test_1_migrator_from_pre_inventory_schema` |
| 2 | Second migrator run idempotent no-op | PASS | `TestMigrator::test_2_second_run_is_noop` |
| 3 | Startup `create_all` cannot create/alter truth tables | PASS | `TestSchemaGuarantees::test_3_app_create_all_cannot_create_or_alter_truth_tables` |
| 4 | `(shop_id, id)` unique keys + composite FKs reject cross-shop refs | PASS (real PG insert rejected by `fk_lot_shop_item`) | `test_4_unique_keys_and_composite_fks_reject_cross_shop` |
| 5 | Numeric money/quantity exact | PASS (`NUMERIC(12,2)` column; round-trips `19.99`) | `test_5_numeric_money_and_quantity_exact` |
| 6 | Concurrent same-key receives → exactly one lot+event | PASS | `test_6_same_key_concurrent_receives_exactly_one_pair` |
| 7 | Concurrent different-key receives → no lost quantity | PASS (total delta = 5 = 2 + 3) | `test_7_different_keys_concurrent_no_quantity_loss` |
| 8 | Cutover racing receive: fully-before-boundary or clean reject, never partial | PASS | `test_8_cutover_racing_receive_never_partial` |
| 9 | Backfill racing/repeating dual-written receive cannot duplicate quantity | PASS | `test_9_backfill_repeat_vs_dual_write_no_double_quantity` |
| 10 | Event-without-lot corruption fails permanently, snapshot unchanged | PASS | `test_10_event_without_lot_fails_permanently_snapshot_intact` |
| 11 | Opening/negative/zero gaps reconcile deterministically | PASS (+3/+5 receive, −5 loss with NO Sale row, zero-gap writes nothing; recon `{}` ×3 shops, rerun-stable) | `test_11_opening_negative_zero_gaps_reconcile` |
| 12 | Rollback drill preserves snapshot, WA cost, Sale rows, PurchaseRecord behavior | PASS | `test_12_rollback_drill_preserves_snapshot_wa_sales_purchase` |
| 13 | Mid-migration failure leaves no partially accepted schema | PASS (injected failure after tables → nothing created; rerun clean) | `test_13_midpoint_migration_failure_leaves_no_partial_schema` |
| 14 | Freeze covers staging/trade/CSV-admin; Sale & Shopify otherwise unchanged | PASS (staging commit raises, trade apply rejects, admin guard 503, POS raises → mapped 503, Sale count unchanged) | `test_14_all_quantity_changing_intake_paths_frozen` |

## Historical backfill — actual result

Backfill A (purchase records) ran against three seeded shops during cutover:

- `shop-pos`: purchase backfill event **delta +5** plus opening-gap event
  **+3** (stock 8 vs purchased 5). Two lots total.
- `shop-neg`: purchase backfill event **+6** plus loss event **−5**
  (stock 1). Loss produced **no Sale row** (asserted).
- `shop-zero`: purchase backfill event **+4**, gap 0 → no opening row.

Reconciliation after cutover returned `{}` (zero mismatches) for all three
shops and remained identical on immediate re-run (deterministic).

Backfill-vs-dual-write collision (criterion 9): live receive wrote first,
then `backfill_purchase_record` repeated three times against the same key —
exactly one lot and one event persisted; reconciliation stayed `{}`.

## CI integration

`.github/workflows/inventory-truth-gates.yml` — blocking PR job
`pg-acceptance`: ephemeral GitHub Actions postgres service container, runs
the same harness via `STASHTAB_PG_URL`. Uses only throwaway CI credentials;
no repository secrets, no production dependency. Triggers on
`services/api/**` and inventory-truth docs paths.

## Bounded verification of corrected criteria

After the corrections above, the entire harness was re-run twice on freshly
created containers (second run = verification pass): both runs
**14 passed** (~34–35 s). Full SQLite regression:
**104 passed** (was 90 before this pass; +14 PG harness tests).

## Result

All fourteen criteria have explicit passing evidence on real PostgreSQL.

`INVENTORY RECEIVE FOUNDATION READY FOR ACCEPTANCE`
