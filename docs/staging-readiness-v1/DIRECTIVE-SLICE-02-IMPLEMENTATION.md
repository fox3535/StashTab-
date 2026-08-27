# Proposed implementation directive — slice-02 inventory schema rehearsal

**Status:** `APPROVED FOR LOCAL IMPLEMENTATION ONLY`  
**Bound by:** D-027 and `PLAN-SLICE-02-INVENTORY-SCHEMA-REHEARSAL.md`  
**Pinned commit:** `d81e7c81aa03d72c1a236c481638808e9d05d759`

Named human approved local implementation on 2026-08-26. Neon, Railway,
Clerk, and production remain locked. Do not enable inventory routes.

## Allowed work

1. Add an explicit live/base migrator that creates only `inventory_item`,
   `purchase_record`, and `sale`, with shop FKs and shop-scoped unique
   `(shop_id, id)` keys, matching current model types.
2. Run the existing inventory-truth migrator after those parents exist.
3. Prove apply, idempotent rerun, injected-failure rollback, grants, and
   API SELECT-only on disposable local PostgreSQL 16.
4. Keep receive, POS, adjust, CSV quantity, Shopify, worker, notifications,
   Web Push, payments, Watch, and production off.

## Forbidden

- Neon, Railway, Clerk, production, or any hosted apply
- Creating other live tables (`staging_item`, `show_sessions`, Shopify,
  settings, outbox, and the rest)
- Granting API INSERT/UPDATE/DELETE/TRUNCATE/DDL
- Any grant to worker or readonly on rehearsal tables
- Startup `create_all` / leftover ALTER
- Dual-write, cutover rows, or route enablement
- Editing frozen contracts

## Stop

If an extra live table appears necessary, stop and cite model, column,
constraint, and failing test. Do not add it for convenience.
