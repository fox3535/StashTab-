# slice-03-adjustments — acceptance record

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.2.0 (frozen)
**Slice:** `slice-03-adjustments`
**Decision:** **APPROVED by human owner, 2026-08-24**
**Status:** `COMPLETED — NOT MERGED — NOT DEPLOYED`

Worktree: `feature/inventory-truth-slice-03` based on planning checkpoint
`6370060`. No merge, push, production schema apply, or production credentials.

## Accepted evidence

| Item | Result |
| --- | --- |
| Frozen contract v1.2.0 hashes and validators | PASS |
| Migrator-only append-only `inventory_adjustment` | PASS |
| Startup `create_all` cannot create the table | PASS |
| Runtime cannot UPDATE, DELETE, or TRUNCATE adjustment history | PASS |
| Locked PATCH/CSV writer | PASS |
| Existing-SKU CSV is atomic | PASS |
| New-item CSV fails without writes | PASS |
| Negative inventory fails without partial mutation | PASS |
| Verified membership; owner-only CSV | PASS |
| Idempotent replay and payload-conflict handling | PASS |
| Reverse-once and actor evidence | PASS |
| After-commit anomaly alerts | PASS |
| Slice-03 tests | 31/31 passed |
| SQLite suite | 105 passed, 25 PostgreSQL-only skipped |
| Full PostgreSQL harness | 25 passed |
| Concurrency rerun | PASS |
| Mutation-path audit | no remaining silent PATCH/CSV quantity overwrite |
| Seven implementation reviews | PASS after CSV failure-response correction |
| Rollback drill | PASS |

## Standing gates carried forward

1. **NOTIFICATION-INTEGRATION-GATE** — blocks merge and deployment.
2. **MIGRATOR-ROLE-PROVISIONING-GATE** — blocks production schema apply and deployment.
3. Human approval before production schema application.
4. Cutover reconciliation must equal zero.
5. Cutover runbook, audit logging, and break-glass procedure.
6. **CSV-COST-FEEDBACK-GATE** — existing-item CSV cost fields remain unapplied. Before production use, the API/import result and eventual interface must explicitly report that cost changes were ignored and require a separately approved cost-correction workflow. They must not be reported as successfully updated.

## Explicitly not done

No merge, push, production migration, new-item CSV, cost correction,
cycle-count UI, bulk reverse, payments, Watch, or frontend work.
