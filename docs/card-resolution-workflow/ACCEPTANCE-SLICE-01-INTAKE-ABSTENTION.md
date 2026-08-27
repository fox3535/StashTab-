# Slice-01 local intake/abstention — acceptance

**Slice:** `card-resolution-core-v1 / intake-abstention-local-v0`  
**Status:** `COMPLETED — NOT MERGED — NOT DEPLOYED — FEATURE OFF`  
**Decision:** D-034  
**Accepted:** named human owner 2026-08-27  
**Freeze checkpoint:** `671f663`  
**Branch:** `feature/card-resolution-intake-abstention-local-v0`  
**This file is not in freeze hashes.** Frozen contract and policy files were not rewritten.

## Accepted local evidence

| Item | Result |
| --- | --- |
| SQLite/API regression | 242 passed |
| Scoring tests | 14 passed |
| HTTP tests | 16 passed |
| Card-resolution PostgreSQL 16 | 3 passed, twice, on fresh containers |
| Live-schema rehearsal PostgreSQL 16 | 15 passed |
| Inventory-truth + notification PostgreSQL | 46 passed |
| Unique tests | 306, plus the three-test clean rerun |
| Freeze, contract, context, compile, secret, artifact | passed |
| Schema | six migrator-owned tables only; startup create-all creates none |
| Runtime grants | catalog SELECT; intake/review SELECT+INSERT+UPDATE; evidence/candidate/audit SELECT+INSERT; worker/readonly/PUBLIC none |
| Append-only | evidence and audit reject UPDATE/DELETE/TRUNCATE |
| Shop scope | composite shop-scoped references; cross-shop insert denied |
| Concurrency | identical concurrent intake is one outcome; review decisions serialized |
| Providers / models | no JustTCG, TCGCSV, Pokémon TCG API, or model path |
| Inventory / pricing | accepted identity writes none |
| Rollback | drops the six new tables; identity and all 13 rehearsal tables remain |
| Staging / production | fail-closed even if other flags are mis-set |

## Explicitly not accepted

Merge to `main`, staging or production schema apply, route enablement,
JustTCG/TCGCSV, inventory promotion, review UI, payments, Watch, or
cloud action.

## Superseded harness evidence

An earlier combined PostgreSQL pytest invocation failed. Rehearsal ran
under the wrong database role, and older inventory-truth/notification
suites targeted an unavailable local port. That record is harness
setup, not a product defect. It was superseded by the separated
PostgreSQL runs above. Do not delete it.

See `reviews/SUPERSEDED-COMBINED-PG-HARNESS.md`.

## Remaining gates

Draft PR review. Merge only after a separate owner instruction. Staging
and production remain off until later named unlocks.
