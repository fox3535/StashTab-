# backend-notification-integration-v1 / implementation-1.1.2 — acceptance record

**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0 + AMENDMENT-1.1.0 (unchanged) + AMENDMENT-1.1.1 frozen + AMENDMENT-1.1.2 frozen  
**Slice:** `backend-notification-integration-v1 / implementation-1.1.2`  
**Decision:** **APPROVED by human owner, 2026-08-25**  
**Status:** `COMPLETED — NOT PUSHED — NOT MERGED — NOT DEPLOYED`

Worktree: `feature/backend-notification-v1.1.2`. No push, merge, production schema apply, live Web Push, or production credentials.

## Accepted evidence

| Item | Result |
| --- | --- |
| PostgreSQL 16.14 disposable environment | PASS |
| Two fresh-container PostgreSQL runs | 21/21 each |
| SQLite regression | 178 passed |
| All 26 bounded PostgreSQL criteria | PASS |
| Safe eight-table to twelve-table upgrade | PASS |
| Atomic/idempotent migrator | PASS |
| Startup `create_all` exclusion | PASS |
| Structural constraint/index/trigger verification | PASS |
| Cross-shop foreign-key rejection | PASS |
| Runtime-role append-only protection | PASS |
| Runtime cannot assume migrator role | PASS |
| Observation, transition, attempt, lease, batching, recovery-park, cancellation, membership, and feature-flag proofs | PASS |
| No real Web Push, external DNS, production data, or production credentials | PASS |

## Merge gate added

**GITHUB-NOTIFICATION-CI-GATE** — The blocking PostgreSQL notification workflow must execute successfully on GitHub against the exact pushed commits before merge or deployment. The unexecuted workflow definition is not execution evidence.

## Standing gates carried forward

1. **GITHUB-NOTIFICATION-CI-GATE** — blocks merge and deployment until remote CI runs green on the pushed commits.
2. **NOTIFICATION-INTEGRATION-GATE** — remaining review of overlapping identity/inventory files before merge.
3. **MIGRATOR-ROLE-PROVISIONING-GATE** — blocks production schema apply and deployment.
4. Human approval before production schema application.
5. Production membership unique index `(shop_id, clerk_user_id)`.
6. Cutover reconciliation must equal zero.
7. Cutover runbook, audit logging, and break-glass procedure.
8. Production VAPID / live Web Push remains disabled.

## Explicitly not done

No push, merge, production migration, live Web Push, frontend settings, service-worker install, or browser permission UX.
