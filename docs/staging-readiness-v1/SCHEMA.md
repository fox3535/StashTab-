# Schema lifecycle

## Who may create what

| Tables | How they appear |
| --- | --- |
| Legacy live (`shops`, `shop_members`, `inventory_items`, `sales`, …) | Today: `init_db()` → `Base.metadata.create_all` plus leftover `ALTER TABLE … IF NOT EXISTS` in `database.py`. **Staging/production API and worker must not run that path.** Operator bootstrap as migrator only, then runtime has no `CREATE`. |
| Inventory-truth (8) | **Only** inventory-truth migrator as migrator. Not slice 0. |
| Notification (12) | **Only** notification migrator apply. Not slice 0. |

Acceptance already in tests: application `create_all` must not create truth or notification tables. Keep that true.

## Slice 0

1. DBA: roles via `sql/provision-staging-roles.sql`.
2. Migrator (operator, not Railway API): create **legacy** live schema only.
3. Verify unique membership index `uq_shop_members_shop_user` on `(shop_id, clerk_user_id)`.
4. Switch API `DATABASE_URL` to `stashtab_api`.
5. Boot API with `create_all` and leftover ALTER **disabled**.
6. `/ready` reports truth/notification schema flags **false**. Truth-dependent writes return `503 FEATURE_NOT_READY`.

## Later order (not slice 0)

4. Inventory migrator: unique `(shop_id, id)` on live item/purchase/sale; then truth tables + composite FKs + append-only/TRUNCATE triggers. One transaction.
5. Notification migrator: twelve tables + reconstruction + triggers/grants. One transaction.
6. GRANT DML to api/worker; SELECT to readonly.
7. Restart on runtime URLs. Prove they cannot DDL.

## Containing leftover `create_all` / ALTER

**Required in slice-0 code** when `APP_ENV` is `staging` or `production`:

- Skip `Base.metadata.create_all`
- Skip `_ensure_columns()` (Gmail/sale leftover ALTERs)
- Fail boot if those functions are reached
- Runtime roles: `REVOKE CREATE ON SCHEMA public`

Local/test may keep `create_all` for developer databases only.

## Append-only reality (named)

Inventory DB triggers today cover `refund_record`, `return_record`, `inventory_adjustment`. Ledger `inventory_event` / `acquisition_lot` are not fully trigger-protected. Staging may accept that as a named limitation after truth apply. Not slice 0.
