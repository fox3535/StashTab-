# Migration rehearsal

All rehearsals use **synthetic** data. No production clone unless a later written approval plus sanitization (strip Shopify tokens, Clerk ids rewritten, no customer PII).

Slice 0 stops after roles + legacy bootstrap + identity smoke. Tracks A (truth/notification migrators), B, and C are later unlocks.

## Tracks

### A — Empty database (required)

1. New Neon DB.
2. Roles as `ROLES.md`.
3. Legacy bootstrap.
4. Confirm truth/notification tables absent. Staging API boot must **not** run `create_all` or leftover ALTER (`SAFEGUARDS.md`).
5. Inventory migrator twice: second run no-op, schema unchanged.
6. Inject failure (`fail_after` hooks already exist) → full rollback, no leftover truth tables.
7. Notification migrator twice + failure injection.
8. Runtime LOGIN proof (`ROLES.md`).

### B — Synthetic pre-foundation (required before inventory cutover in staging)

1. Empty path A through legacy bootstrap only.
2. Load synthetic shops, members, items, purchases, sales (no real Shopify).
3. Run inventory migrator.
4. Per-shop freeze + gen-1 cutover (see `CUTOVER.md`).
5. Recon = 0.
6. Repeat migrators (idempotent).

### C — Backup / restore drill (required before calling staging “operable”)

1. Neon PITR or logical dump after a known synthetic state.
2. Restore to a **third** throwaway database.
3. Re-run recon and identity smoke.
4. Record time-to-restore and who can do it.

## Rollback of a failed migrator run

- Transactional migrators already roll back on injected failure (tests).
- After a **successful** apply, rollback is **not** DROP TABLES. Staging rollback = keep tables, keep flags off, restore from backup if data is wrong.
- Dual-write off / freeze remains as in `MIGRATION.md`.

## Who runs rehearsals

A named human with migrator credentials, from a workstation or a one-off job, **not** from the always-on API/worker.
