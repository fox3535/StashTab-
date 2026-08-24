# slice-02-outbound-events — acceptance record

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.1.0 (frozen)
**Slice:** `slice-02-outbound-events`
**Decision:** **APPROVED by human owner, 2026-08-24**
**Status:** `COMPLETED — NOT MERGED — NOT DEPLOYED`

Worktree: `feature/inventory-truth-slice-02` based on checkpoint `132f0f5`.
No merge, push, production schema apply, or production credentials.

## Accepted evidence

| Item | Result |
| --- | --- |
| PostgreSQL runtime role cannot UPDATE, DELETE, or TRUNCATE append-only history | PASS — row triggers plus `BEFORE TRUNCATE` trigger and privilege revoke; runtime role denied |
| Failed destructive attempts preserve all records | PASS — rejected UPDATE/DELETE/TRUNCATE left every row intact |
| Only the controlled migrator role can perform authorized lifecycle operations | PASS — `STASHTAB_TRUTH_MIGRATOR_ROLE` granted TRUNCATE; other roles revoked |
| Migration remains atomic and idempotent | PASS — single transaction; rerun is a no-op; injected midpoint failure leaves no partial schema |
| Startup `create_all` creates no truth tables | PASS — application metadata still excludes all inventory-truth tables |
| Poisoned lines, orders, and shops are isolated | PASS — later valid lines, later orders, and other shops continue |
| Scheduler survives failures and later ticks run | PASS — failed tick is reported; next scheduled tick runs |
| Retries cannot double-decrement | PASS — observation ledger + unique keys; committed events stay committed |
| Alert failures cannot roll back or resolve exceptions | PASS — delivery is after commit; failure leaves the exception open |
| Focused PostgreSQL checks | 24/24 twice on fresh disposable containers |
| Complete PostgreSQL-enabled suite | 98 passed |
| SQLite suite | 74 passed, 24 PostgreSQL-only tests skipped |
| Corrected-criteria verification | 57 passed |
| Validators and compile checks | PASS |

## Standing gates carried forward

1. Human approval before any production schema application.
2. Production membership unique index `(shop_id, clerk_user_id)`.
3. Cutover reconciliation must equal zero (timeout is not green).
4. Cutover operations runbook, audit logging, and break-glass procedure.
5. **NOTIFICATION-INTEGRATION-GATE** — slice-02 `main.py` / `worker.py` (and overlapping files) must be reconciled with the preserved notification implementation before merge or deployment. Import removals are not deletion of that work. Both outbound processing and notifications must pass together after integration. **BLOCKS merge and deployment.**
6. **MIGRATOR-ROLE-PROVISIONING-GATE** — before production schema application, prove the migrator role is deliberately provisioned and reviewed; production does not silently create an unexpected privileged role; the runtime role cannot assume, inherit, grant, or authenticate as the migrator; no migrator credentials live in application configuration or runtime containers; migrator access is time-bounded and audited; the runtime role still fails UPDATE/DELETE/TRUNCATE. Does **not** block accepting this isolated implementation. **BLOCKS production schema application and deployment.**
7. Manual-resolution workflow for duplicate suspicions before production outbound cutover.
8. Adjust slice completed before production inventory-truth cutover.

## Explicitly not done

No merge, push, pull request, production migration, or production credentials.
Admin PATCH and CSV absolute quantity overwrites remain frozen until the
adjust slice. Notification modules remain in the main working tree and are
not part of this checkpoint.
