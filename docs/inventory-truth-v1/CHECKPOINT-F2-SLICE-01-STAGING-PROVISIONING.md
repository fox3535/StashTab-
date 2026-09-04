# Checkpoint — F2 slice-01 staging provisioning (prepared, not executed)

**Status:** `PREPARED — NOT EXECUTED — AWAITING NAMED PROVISIONING UNLOCK`
**Code on `main`:** `a354fed0570241894b6e866e9e18ffbb059add6f` (merge of PR #31)
**Head included:** `8fa58cb` (implementation `af9431b` + correction `feb94d6` + acceptance)
**Bound by:** AMENDMENT-1.3.0 §4/§7 and DIRECTIVE-F2 unlock 3 only
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

This checkpoint describes the exact staging Neon apply. It does **not**
authorize execution. Cutover and receive-endpoint use stay separately locked.

## Target (when unlocked)

| Item | Value |
| --- | --- |
| Database | Neon `stashtab_staging` only |
| Role | `stashtab_migrator` only (runtime never applies schema) |
| Command | `python -m app.inventory_live_schema.migrator apply-f2-receive` |
| Function | `apply_f2_receive` |

## Additive objects (opt-in, one transaction)

1. Column `purchase_record.client_idempotency_key` `VARCHAR(36)` nullable.
2. Partial unique index `uq_purchase_record_shop_client_key` on
   `(shop_id, client_idempotency_key)` where the key is not null.
3. Least-privilege envelope for `stashtab_api`:
   - `inventory_item`: SELECT, INSERT, `UPDATE (stock, cost)` only
   - `purchase_record`, `acquisition_lot`, `inventory_event`: SELECT, INSERT
   - USAGE on the four identity sequences
4. Per-table policy assert after grants.

Rerun is a no-op. Injected mid-failure must leave nothing partial.
No DELETE, TRUNCATE, DDL, ownership change, or migrator assumption for
the runtime role.

## Evidence-preserving rollback (not a drop)

`python -m app.inventory_live_schema.migrator rollback-f2-receive-grants`

Revokes the envelope back to SELECT-only. Keeps the column, index, and
every evidence row.

## Explicitly not this checkpoint

- Cutover unlock (gen-1 synthetic shop)
- Using `POST /api/v1/admin/inventory/receive` on staging
- Railway/API redeploy
- Production schema, privileges, or data
- Clerk, worker, Shopify, notifications, frontend receive UI
- Contacting Neon/Railway/Clerk until a named owner unlock

## Owner-accepted freeze baseline (unchanged)

`FREEZE-1.3.0.json` is historical machine-byte evidence and does not
validate against the current LF Git checkout. `FREEZE-1.3.0-git-canonical.json`
is the authoritative repository/CI record. PR #31 changed none of the
five frozen packet files. Neither manifest is modified here.
