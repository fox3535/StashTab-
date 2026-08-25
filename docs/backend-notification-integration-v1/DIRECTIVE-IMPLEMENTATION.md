# IMPLEMENTATION DIRECTIVE (PREPARED — NOT EXECUTED)

**Slice:** `backend-notification-integration-v1`
**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0 + AMENDMENT-1.1.0 (policy) + AMENDMENT-1.1.1 (mechanics, frozen) + AMENDMENT-1.1.2 (observation/transition/attempt/park, frozen)
**Plan:** `DIRECTIVE.md` (frozen 1.1.1) plus AMENDMENT-1.1.2
**Status:** `PREPARED — DO NOT EXECUTE until a new named implementation unlock for 1.1.0+1.1.1+1.1.2`
**Does not authorize code, copy, migrations, merge, push, deploy, or Web Push**

The 1.1.1 unlock does **not** authorize this combined slice.

## Bound

Smallest backend integration onto `feature/inventory-truth-slice-03` @ `3a78278`.
Python/FastAPI owns writers. Every query is `shop_id` scoped. Identity is
verified JWT + membership. Web Push stays off without complete VAPID.

## Required work (when unlocked)

Preserve every previously frozen 1.1.1 requirement, then add 1.1.2:

1. Controlled notification schema migrator (`apply_notification_schema()`),
   one transaction, idempotent, not `create_all`, separate from inventory-truth.
   Reconstruct 1.1.2 columns/tables per AMENDMENT-1.1.2 §7 (`WHERE NOT EXISTS`,
   never overwrite live counters).
2. Adapted backend models and logic for 1.1.1 tables plus 1.1.2:
   `notification_source_observation`, `notification_occurrence_transition`,
   `notification_delivery_attempt`, `notification_recovery_park`.
3. Verified notification router: JWT + membership; headers untrusted.
4. Always-running isolated notification worker tick (runs when Shopify
   auto-sync is off; one shop failure cannot stop others; own session).
5. Durable-source recovery sweep (pattern B token `initial` only) plus
   same-txn outbox (pattern A) per AMENDMENT-1.1.1 §7.
6. Explicit retry/terminal states: `pending`, `retry_scheduled`, `sent`,
   `failed_exhausted`, `expired`, `cancelled`.
7. Queue fairness: oldest-due first via `COALESCE(next_retry_at, created_at)`;
   future retries skipped; exhausted rows never re-selected.
8. Safe test-send backend: unique `dedupe_key` per request UUID, rate-limited
   in the same transaction, audited, quiet-hours bypass only; cannot mutate
   real events.
9. Identity test reconciliation: restore notification stubs without undoing
   fail-closed identity assertions.
10. Backend notification tests and PostgreSQL harness, including crash/
    sweep/uniqueness and at-least-once duplicate-push non-mutation.
11. Manual reconciliation of overlapping backend files (`main.py`,
    `worker.py`, `deps.py`, identity tests, requirements) with the
    original-worktree sources. Do not blind-copy. Do not drop inventory
    routers or worker isolation.

## Added 1.1.2 acceptance tests (required)

- Same observation token is a no-op; second apply does not increment
  `occurrence_count` or create deliveries.
- Distinct tokens on an active event increment `occurrence_count` and do
  not create a new occurrence or delivery generation.
- Pattern-B recovery with token `initial` does not mint tokens or reopen.
- Transition current status is max `transition_seq`; NULL→pending then
  pending→delivered|failed|cancelled only.
- Concurrent terminal writers: one terminal row; loser does not insert seq 3.
- After ack/resolve, last device still writes occurrence delivered/failed.
- Cancelled event cannot later go delivered/failed; next tick creates no
  new deliveries.
- Attempt log is append-only `started` then `outcome`; `outcome` without
  `started` is rejected.
- Crash after `started`: wait until `claimed_until` expires, write
  `provider_unknown`, then retry on `attempt_count+1`. In-lease send is
  not recovered as a crash.
- Shop A send after shop A membership delete fails even if the user remains
  in shop B.
- Owner cancel is 401/404/403 as specified; staff cannot cancel.
- Two authorized test-sends create two events; sixth in window is 429.
- Poison park: 100 failing sources do not hide a later healthy source;
  parked sources still recover after `next_at`.
- Incomplete materialization cannot close an occurrence.
- Invalid timezone and revoked members are omitted from the due batch.
- TLS pin connects to validated IP with original hostname verification.
- Attempt `error` stores no endpoint, key, or raw provider body.

## Out of scope

Frontend settings, service-worker install, browser permission UX, production
VAPID credentials, real push sends, deployment, inventory feature changes.

## Transport rule (D-N5)

At-least-once. Payloads and click actions idempotent and non-mutating.
Duplicate delivery cannot alter inventory, adjustment, card-resolution, or
security events. Do not claim exactly-once. Audit retry and outcome.

## Rollback

Flag off; unmount router; skip tick. Tables may remain. Do not overwrite
`FREEZE-1.1.1.json` or `FREEZE-1.1.2.json`. Inventory schema untouched.

## Unlock required

Named human `implementation_unlock` for
`backend-notification-integration-v1` covering 1.1.0+1.1.1+1.1.2.
Until then this file is not an execution order.
