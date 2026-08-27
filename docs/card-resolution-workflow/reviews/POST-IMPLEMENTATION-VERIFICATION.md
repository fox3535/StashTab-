# Final verification — local intake/abstention

Acceptance verification against freeze `671f663`, contract 1.0.0, and
`identity-score-v0`. Local implementation is accepted as D-034:
`COMPLETED — NOT MERGED — NOT DEPLOYED — FEATURE OFF`.

## Tests

- Frozen hashes and contract/context validators: all green, including
  identity-score tamper proof.
- Full SQLite/API regression (excluding separately launched PostgreSQL
  suites): 242 passed.
- Card-resolution scoring: 14 passed.
- Card-resolution HTTP: 16 passed.
- Card-resolution PostgreSQL 16: 3 passed, twice, on fresh containers.
- Inventory live-schema rehearsal PostgreSQL 16: 15 passed.
- Inventory-truth + notification PostgreSQL acceptance on disposable
  `postgres:16` at `127.0.0.1:55432/stashtab_it`: 46 passed.

## Slice-local corrections in this verification

- Review decisions are serialized; contradictory terminals return 409.
- Audit rows use shop-scoped composite foreign keys.
- Rollback proof covers identity plus all 13 staging-rehearsal tables.
- Runtime cannot UPDATE/DELETE/TRUNCATE evidence or audit; cross-shop
  evidence insert fails.
- Staging/production remain fail-closed even if debug and notifications
  are mis-enabled.

## Remaining deployment gates

- Staging/production schema and flag enablement.
- JustTCG/TCGCSV, inventory promotion, review UI.

PR #13 is merged to `main` `6a266b1`. Feature remains off.

## Superseded harness

An earlier combined PostgreSQL pytest run failed because rehearsal used
the wrong role and older suites targeted a dead port. That record is
harness evidence, not a product defect. See
`SUPERSEDED-COMBINED-PG-HARNESS.md`.
