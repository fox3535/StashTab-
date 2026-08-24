# IMPLEMENTATION DIRECTIVE (PREPARED — NOT EXECUTED)

**Slice:** `inventory-truth-v1 / slice-03-adjustments`
**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.2.0 (frozen)
**Plan:** `DIRECTIVE-SLICE-03.md` (frozen against v1.2.0)
**Status:** `PREPARED — DO NOT EXECUTE until a named implementation unlock`
**Does not authorize code, migrations, merge, push, or deploy**

## Bound

Replace silent absolute quantity overwrites (admin PATCH stock, CSV
quantity on existing SKUs) with one locked read → signed delta → event +
`inventory_adjustment` + snapshot write. Preserve the display snapshot.
Do not create inventory from CSV. Do not change cost. Do not implement
cycle-count campaign UI, CSV receive, bulk reverse, payments, Watch, or
notification delivery.

Python/FastAPI owns the writer. Every query is `shop_id` scoped. Identity
is verified token + membership.

## Required work (when unlocked)

1. Migrator-only `inventory_adjustment` per AMENDMENT-1.2.0 (append-only,
   TRUNCATE deny, not in `create_all`).
2. Single adjust writer used by PATCH and CSV: lock row, compute delta,
   reject negative remaining, insert event+evidence+snapshot atomically.
3. PATCH: `stock` or `stock_delta`, required `reason_code` and
   `Idempotency-Key` UUID. Price-only PATCH unchanged.
4. CSV: owner-only, validate whole file, one transaction. Duplicate SKU
   rules. New-item row fails the file. Existing cost columns ignored.
5. Reverse: one opposite event, both actors, unique on original, fail if
   remaining would go negative.
6. `adjust_anomaly` after commit; no stack on retry; failure cannot roll
   back. Defaults: |delta|≥100; or ≥50% of on-hand when on-hand≥10; or
   more than 10 adjusts per SKU per shop per 24h.
7. Freeze: quantity PATCH/CSV 503; price-only allowed; mixed fails.
8. Tests in AMENDMENT-1.2.0 §13, including PG concurrency twice.
9. Grep gate: remaining `stock=` writers are receive, sell, reverse of
   those, and this one writer.

## Out of scope

CSV new-item/receive, cost correction, cycle-count campaigns, bulk
reverse, reverse-of-reverse, production DDL, merge, deploy.

## Rollback

Stop dual-write; snapshot/Sale/PurchaseRecord unchanged; adjustment rows
stay as evidence. Do not overwrite `FREEZE-1.2.0.json`.

## Unlock required

Named human `implementation_unlock` for `slice-03-adjustments`. Until
then this file is not an execution order.
