# F2 slice-01 controlled receive — local acceptance record

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.3.0 (AMENDMENT-1.3.0 frozen)
**Slice:** `f2-slice-01-controlled-receive`
**Branch:** `implementation/f2-slice-01-controlled-receive`
**Implementation commit:** `af9431b`
**Correction commit:** `feb94d6` (column-scoped UPDATE grant fix)
**Decision:** **APPROVED by human owner, 2026-08-31**
**Status:** `IMPLEMENTED LOCALLY — NOT MERGED — NOT DEPLOYED — PRIVILEGES/CUTOVER UNCHANGED`

No merge, push to production, staging schema apply, privilege cutover,
Railway/Neon/Clerk contact, or staging writes occurred during acceptance.

## PostgreSQL evidence (disposable local `postgres:16`)

| Suite | Result |
| --- | --- |
| F2 controlled receive (`test_f2_receive_pg.py`) | **12/12 passed** (receive flow parametrized twice on fresh DBs) |
| Identity migrator (`test_identity_schema_migrator.py`) | **12/12 passed** |
| Live-schema rehearsal (`test_inventory_live_schema_rehearsal.py`) | **15/15 passed** |
| Inventory-truth PG acceptance (`test_pg_acceptance.py`) | **25/25 passed** |
| Notification PG (`test_notification_pg.py`, `test_notification_pg_112.py`) | **21/21 passed** |
| Clean `main` at `9870468` PG baseline (same suites, no F2 file) | **73/73 passed** |

Harness notes: inventory-truth and notification PG suites used local
`STASHTAB_PG_URL` against disposable `postgres:16` on port 55432;
F2/identity/rehearsal suites used per-test fresh Docker containers.

## SQLite / API evidence

| Suite | Result |
| --- | --- |
| F2 controlled receive (`test_f2_receive.py`) | **18/18 passed** |
| Broader SQLite/API regression (PG-docker suites excluded) | **263/263 passed** |

## Defect and correction mapping

| Defect | Classification | Correction |
| --- | --- | --- |
| F2 migrator `_assert_f2_policy` failed: `inventory_item.id` retained UPDATE after envelope apply | Branch-only; PostgreSQL 16 `has_column_privilege` stays true for all columns after table-level `GRANT UPDATE` even after column `REVOKE` | `feb94d6`: `REVOKE UPDATE ON TABLE` then `GRANT UPDATE (stock, cost)` only; table-level assert expects SELECT+INSERT; column assert verifies stock/cost |
| Inventory-truth grep gate flagged `controlled_receive.py` stock mutation | Branch-only; new receive path outside slice-02 O-list | `feb94d6`: allow `item.stock = total_qty` in `test_pg_acceptance.py` |
| 46 PG skips without `STASHTAB_PG_URL` | Environmental setup; identical on branch and clean `main` | Resolved by approved local disposable Postgres target |

## Exact permission proof

Runtime role `stashtab_api` after F2 envelope (verified in PG harness):

| Object | Privileges |
| --- | --- |
| `inventory_item` | SELECT, INSERT; UPDATE only on columns `stock`, `cost` (no table-wide UPDATE) |
| `purchase_record` | SELECT, INSERT |
| `acquisition_lot` | SELECT, INSERT |
| `inventory_event` | SELECT, INSERT |
| Other rehearsal tables | SELECT only |
| `stashtab_worker`, `stashtab_readonly` | No table privileges on envelope objects |
| Sequences on envelope tables | USAGE granted to `stashtab_api` |
| `SET ROLE stashtab_migrator` | Denied for runtime role |

Rollback of grants restores SELECT-only while preserving column, index,
and evidence rows (§12 policy).

## SQLSTATE 42501 scope

`operational_error_handler` maps **only** `InsufficientPrivilege` /
SQLSTATE `42501` to controlled 503 `FEATURE_NOT_READY`. Other
`OperationalError` paths re-raise. `ProgrammingError` maps to 503 only
when `is_missing_relation` (undefined table). Verified in F2 SQLite
acceptance and handler design review.

## Bounded review

One Bugbot review of correction pass (`feb94d6`): no findings.

## Explicitly not done

Staging Neon apply, production migration, privilege cutover, gen-1
cutover on synthetic shop, frontend receive UI, merge to `main`,
deploy, worker/Shopify/notifications enablement, and any cloud contact.

`lib/use-api-auth.ts` and seven barcode PNGs remain untracked and untouched.
