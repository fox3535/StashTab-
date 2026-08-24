# IMPLEMENTATION DIRECTIVE (PREPARED — NOT EXECUTED)

**Slice:** `backend-notification-integration-v1`
**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0 + AMENDMENT-1.1.0 (policy) + AMENDMENT-1.1.1 (mechanics, frozen)
**Plan:** `DIRECTIVE.md` (frozen)
**Status:** `PREPARED — DO NOT EXECUTE until a named implementation unlock`
**Does not authorize code, copy, migrations, merge, push, deploy, or Web Push**

## Bound

Smallest backend integration onto `feature/inventory-truth-slice-03` @ `3a78278`.
Python/FastAPI owns writers. Every query is `shop_id` scoped. Identity is
verified JWT + membership. Web Push stays off without complete VAPID.

## Required work (when unlocked)

1. Controlled notification schema migrator (`apply_notification_schema()`),
   one transaction, idempotent, not `create_all`, separate from inventory-truth.
2. Adapted backend models and logic for AMENDMENT-1.1.1 tables, durable
   `notification_source`, occurrence, and per-device delivery rows.
3. Verified notification router: JWT + membership; headers untrusted.
4. Always-running isolated notification worker tick (runs when Shopify
   auto-sync is off; one shop failure cannot stop others; own session).
5. Durable-source recovery sweep (pattern B) plus same-txn outbox (pattern A)
   per AMENDMENT-1.1.1 §7.
6. Explicit retry/terminal states: `pending`, `retry_scheduled`, `sent`,
   `failed_exhausted`, `expired`, `cancelled`.
7. Queue fairness: oldest-due first; future retries skipped; exhausted rows
   never re-selected.
8. Safe test-send backend: labeled, rate-limited, audited, quiet-hours bypass
   only; cannot mutate real events.
9. Identity test reconciliation: restore notification stubs without undoing
   fail-closed identity assertions.
10. Backend notification tests and PostgreSQL harness, including crash/
    sweep/uniqueness and at-least-once duplicate-push non-mutation.
11. Manual reconciliation of overlapping backend files (`main.py`,
    `worker.py`, `deps.py`, identity tests, requirements) with the
    original-worktree sources. Do not blind-copy. Do not drop inventory
    routers or worker isolation.

## Out of scope

Frontend settings, service-worker install, browser permission UX, production
VAPID credentials, real push sends, deployment, inventory feature changes.

## Transport rule (D-N5)

At-least-once. Payloads and click actions idempotent and non-mutating.
Duplicate delivery cannot alter inventory, adjustment, card-resolution, or
security events. Do not claim exactly-once. Audit retry and outcome.

## Rollback

Flag off; unmount router; skip tick. Tables may remain. Do not overwrite
`FREEZE-1.1.1.json`. Inventory schema untouched.

## Unlock required

Named human `implementation_unlock` for `backend-notification-integration-v1`.
Until then this file is not an execution order.
