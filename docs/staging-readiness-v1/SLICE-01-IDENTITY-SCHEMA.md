# Slice-01 identity schema (local package)

**Baseline:** `9eaea29d0dcd49deef7a30dae8c2191bfd474899`  
**Owner decisions:** approved, pending separate Neon execution.

## Kernel

Only `shops` and `shop_members`. Live names: `shop_members`, `clerk_user_id`.

Types match the compiled SQLAlchemy models: `VARCHAR(36)` ids, `VARCHAR(120)` text, `VARCHAR(32)` role, `TIMESTAMP WITH TIME ZONE` timestamps, no sequences, no database defaults.

Constraints: `uq_shops_slug`, `uq_shop_members_shop_user`, `fk_shop_members_shop_id`, `ck_shop_members_role` (`owner` or `staff`).

## Privileges

Verified identity routes need SELECT and INSERT only. `stashtab_api` gets those two operations. Worker and readonly get no DML. Startup in staging still creates no schema.

The migrator does not change database role membership. Before any DDL it checks that api, worker, and readonly cannot assume the migrator, and fails closed if they can.

On objects it owns, it revokes all table privileges from PUBLIC, api, worker, and readonly, then grants api SELECT and INSERT only. It also revokes its own default table privileges so later tables do not inherit broad API DML. Verification uses effective privileges, not grant presence alone.

## Commands (local / operator)

```text
python -m app.identity_schema apply
python -m app.identity_schema rollback
```

Rollback drops `shop_members` then `shops`. It does not drop roles. Neon apply is not authorized by this slice.
