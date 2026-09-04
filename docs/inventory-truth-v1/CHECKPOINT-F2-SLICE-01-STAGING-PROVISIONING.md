# Checkpoint — F2 slice-01 staging provisioning (executed, reconciled and verified)

**Status:** `EXECUTED ON STAGING — RECONCILED AND VERIFIED — CUTOVER STILL LOCKED`
**Code on `main`:** `a354fed0570241894b6e866e9e18ffbb059add6f` (merge of PR #31)
**Head included:** `8fa58cb` (implementation `af9431b` + correction `feb94d6` + acceptance)
**Bound by:** AMENDMENT-1.3.0 §4/§7 and DIRECTIVE-F2 unlock 3 only
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

This checkpoint was **executed on staging** under the named provisioning
unlock, then reconciled and verified read-only. Cutover and receive-endpoint
use stay separately locked.

## Execution and reconciliation record (2026-09-04)

- Provisioning was applied during an **authorized Cursor run** that was
  interrupted (usage limit) before it reported. This is reconciliation of an
  authorized action, **not** a governance incident.
- Qoder **reconciled and verified** the live staging state read-only against
  this checkpoint. Every item matched.
- **Applied objects (verified present on `stashtab_staging`):**
  - Column `purchase_record.client_idempotency_key` `character varying(36)`,
    nullable.
  - Partial unique index `uq_purchase_record_shop_client_key` on
    `(shop_id, client_idempotency_key)` where the key is not null.
  - `stashtab_api` envelope: SELECT + INSERT on `inventory_item`,
    `purchase_record`, `acquisition_lot`, `inventory_event`; column-scoped
    `UPDATE (stock, cost)` on `inventory_item` only; no table-wide
    UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER; USAGE on the four F2 sequences.
  - The other seven rehearsal tables remain SELECT-only. `stashtab_worker`,
    `stashtab_readonly`, and PUBLIC hold no envelope rights, and no role can
    assume `stashtab_migrator`. All F2 objects are owned by `stashtab_migrator`.
- **Data state (unchanged):** every business/truth table holds `0` rows;
  identity is intact at `2` shops / `2` owners; no `F2-TEST-0001`; cutover
  rowcount `0` (OFF). No receive call and no partial business-data write.
- **Idempotent rerun:** a single `apply-f2-receive` returned `columns: []`,
  `indexes: []` (nothing created; both already present) and re-affirmed grants.
  Before/after read-only snapshots were **byte-identical** (SHA-256
  `c5f5eafb196d85a47fe56062c5472245de2831cfd1c90cc456c368ef7e7f087b`).
- **Not done:** no rollback (would de-provision), no deployment, no seed, no
  receive, no cutover, no production action.
- **Credential hygiene:** the staging migrator URL file was securely destroyed
  (overwritten in place to zero non-zero bytes, then deleted). It is neither
  committed nor printed here.

Two **pre-existing non-F2** privilege observations were recorded as follow-ups
(not F2 claims) in `GATES-POINTER-F2-SLICE-01.md`.

## Target (as applied on staging)

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
