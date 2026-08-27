# Slice-02 local implementation — bounded review

**Head:** local `feature/staging-inventory-schema-rehearsal` after implementation.  
**Base:** `main` `d81e7c81aa03d72c1a236c481638808e9d05d759`  
**Budget:** one review, one correction if needed, one verification. No further planning.

## Architecture

Live parents are created by an explicit SQL migrator, not `create_all`.
Truth DDL still uses the committed truth migrator after those parents exist.
No extra live tables. `Sale.show_session_id` has no FK. Routes are unchanged.

## Partner-Python / domain parity

SKU, purchase, and sale snapshots stay on the three live parents. Dual-write,
staging dock, Shopify, and wipe helpers are not activated. Mapping:
`SLICE-02-PARTNER-MAP.md`.

## Database security

Migrator owns rehearsal objects. After normalize: API SELECT only; worker and
readonly none; PUBLIC none. Default privileges are revoked for PUBLIC and
runtime roles. API cannot assume `stashtab_migrator`. Sequences are not granted
to API.

## Data integrity

Model types are copied into explicit PostgreSQL DDL. Unique `(shop_id, sku)`
on items. Frozen unique `(shop_id, id)` on all three parents before truth
composite FKs. Shop FKs are `ON DELETE RESTRICT`.

## Tenant isolation

Unknown `shop_id` fails the shop FK. Cross-shop lot/item and event/sale
composite FKs fail. Identity rows stay shop-scoped.

## Concurrency / adversarial

Injected failure after live tables, uniques, and FKs leaves identity only.
Truth injected failure after indexes, tables, or triggers leaves live parents
and identity. Second apply is a no-op. API cannot INSERT/UPDATE/DELETE/
TRUNCATE/DDL.

## Operations / rollback

Truth tables drop first, then sale, purchase_record, inventory_item. Live
rollback refuses while truth remains. `shops`, `shop_members`, and roles
remain. Identity `apply()` is not re-run after extra tables exist.

## Workflow liveness

Implementation, this review, tests, then accept/reject. No extra planning
loop. Hosted apply and route enablement stay locked.

## Evidence

- `pytest tests/test_inventory_live_schema_rehearsal.py`: 15 passed
- existing API suite: 212 passed, 46 skipped (PG jobs without env), 15 deselected
- identity PG: 12 passed
- `test_pg_acceptance.py` + notification PG with local disposable Postgres 16:
  46 passed
