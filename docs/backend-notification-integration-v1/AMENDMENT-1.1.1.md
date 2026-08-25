# AMENDMENT-1.1.1 — Backend notification mechanics

**Identifier:** `STASHTAB-CARD-RESOLUTION-001 / AMENDMENT-1.1.1`  
**Parent:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0 (unchanged)  
**Product-policy record (unchanged):** `docs/card-resolution-workflow/AMENDMENT-1.1.0.md`. **This file does not edit 1.1.0.**  
**Resulting policy set:** 1.1.0 items 1–10 **plus** this 1.1.1 mechanics set.  
**Status:** `APPROVED AND FROZEN`  
**Proposed:** `2026-08-24`  
**Approved:** `2026-08-24`  
**Freeze manifest:** `docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`  
This file does not store its own SHA-256.  
**Implementation:** disabled until named implementation unlock  
**Frontend:** out of scope  
**Baseline:** `feature/inventory-truth-slice-03` @ `3a78278`

## 0. Closed owner decisions (approved 2026-08-24)

D-N1 Retention, D-N2 owner-only critical disable, D-N3 uniqueness
`(shop, occurrence, subscription, delivery_generation)`, D-N4
authorized test-send may bypass quiet hours.

D-N5 **At-least-once transport (binding, approved with this freeze).**
Web Push transport is at-least-once where provider acknowledgement cannot
be made atomic with local state. A crash after provider success but before
local `sent` may cause a safe duplicate notification. Notification payloads
and click actions must be idempotent and non-mutating by default. A
duplicate delivery cannot duplicate, acknowledge, resolve, reopen, or
otherwise alter the underlying inventory, adjustment, card-resolution, or
security event. Use provider-supported idempotency where available, but do
not claim exactly-once delivery when it cannot be proven. Audit the retry
and resulting transport outcome.

## 1. Exact clauses added (1.1.0 items 1–10 unchanged)

11. User notification APIs authenticate with verified JWT + shop membership. Shop/user headers are not credentials.
12. Background delivery uses persisted `Shop.id` only.
13. Notification ticks run even when Shopify auto-sync is off.
14. One shop’s failure cannot stop other shops’ notification ticks.
15. Due work is oldest-due first. Future `next_retry_at` rows are skipped, not selected as the whole batch. Bounded backoff cannot starve other due events.
16. Per-device uniqueness is database-enforced as  
    `(shop_id, event_id, occurrence_seq, subscription_id, delivery_generation)`.  
    Same-occurrence retry **reuses** that identity (UPDATE attempt fields). A genuine reopen creates a new `occurrence_seq` (and `delivery_generation = 1` for new delivery rows) and **does not DELETE** prior deliveries. In-memory locks are never the correctness mechanism.
17. One device `sent` and another `failed_exhausted`/`expired` must not leave the **event/occurrence** `pending` if no device is still `pending` or `retry_scheduled`. If any device `sent` → occurrence `delivered`. If all devices terminal and none sent → occurrence `failed`.
18. **Durable intent.** “After-commit emit” means **transport** starts after the business commit. It is **not** an in-memory callback that is the only copy of the alert. Every critical source must use a durable pattern in §7. A crash after business commit cannot permanently lose the alert. Recovery must not create duplicate occurrences. Transport failure never rolls back inventory, sales, adjustments, or exceptions. Notification-table unavailability cannot mark an underlying exception resolved. A periodic recovery sweep repairs missing occurrences from eligible durable sources using a shop-scoped unique source key.
19. Ack/resolve of a notification never resolves inventory or security exceptions.
20. Schema is migrator-owned, atomic, idempotent. Startup `create_all` must not create or alter these tables in production.
21. Tests use no production credentials, live providers, or real VAPID keys.
22. Unresolved **critical** events are retained until resolved or superseded by an approved lifecycle. Critical event + ack/reopen/resolve + actor audit: **≥ 365 days**. Terminal per-device delivery/transport rows: **90 days**. Expired/replaced subscription transport records: removable after **90 days** unless legal hold or open investigation. Full sensitive payloads are not stored. Defaults may later be lengthened by a formal policy; there is **no forever-retention default**.
23. Only a verified **shop owner** may disable a shop-level critical-alert category. Disable requires explicit confirmation and an audit row (actor, shop, category, timestamp, prior/new state). Staff may manage their own devices and noncritical prefs. Delivery failure or unsubscription cannot change shop-level critical policy.
24. A user-requested **test send** may bypass quiet hours. It must be labeled `category=test`, rate-limited, authorized, and audited separately. It cannot ack/reopen/resolve/alter a real event. Automated/background notifications never use the test bypass.
25. **At-least-once transport.** Web Push is at-least-once when provider acknowledgement cannot be atomic with local `sent`. A crash after provider success and before local `sent` may deliver a safe duplicate. Payloads and click actions are idempotent and non-mutating by default. Duplicate delivery cannot duplicate, acknowledge, resolve, reopen, or alter the underlying inventory, adjustment, card-resolution, or security event. Provider idempotency is used when available. Exactly-once delivery is not claimed. Retry and transport outcome are audited.

## 2. Event / occurrence state machine

Event statuses: `pending`, `delivered`, `failed`, `acknowledged`, `resolved`, `cancelled`.  
Occurrence statuses: `pending`, `delivered`, `failed`, `cancelled`.

- Create (non-routine): event `pending`, occurrence_seq=1 `pending`.
- Routine: event `recorded` (no push).
- Worker finalizes the **current occurrence** per clause 17.
- Member: event `pending|delivered|failed` → `acknowledged`; `acknowledged` → `resolved`.
- Owner: event → `cancelled` (open deliveries of current occurrence → `cancelled`).
- Reopen: new `occurrence_seq`; event → `pending`; prior occurrences and deliveries kept.

Ack/resolve/cancel **do not** mutate `inventory_exception` or other business tables.

## 3. Per-device delivery states (exact)

| Status | Terminal? | Meaning |
| --- | --- | --- |
| `pending` | no | due now or never attempted |
| `retry_scheduled` | no | last attempt failed; `next_retry_at` in the future |
| `sent` | yes | provider accepted this generation |
| `failed_exhausted` | yes | `attempt_count >= max_attempts` |
| `expired` | yes | 404/410 or subscription disabled/replaced |
| `cancelled` | yes | occurrence/event cancelled before send |

Retry: `pending` or due `retry_scheduled` → increment `attempt_count`, send. On retryable transport error: if attempts remain → `retry_scheduled` + backoff; else `failed_exhausted`.  
Same occurrence retry **reuses** unique identity. `max_attempts = 8`. Backoff `min(3600, 30 * 2^(attempt-1))` seconds.

Occurrence terminalization:

- Any device `sent` and none `pending`/`retry_scheduled` → occurrence `delivered` (even if others `failed_exhausted`/`expired`).
- Zero enabled subscriptions at dispatch: occurrence `failed` (no device); recovery may create deliveries if a subscription appears before expiry policy.
- Subscription expires mid-retry: that delivery → `expired`; remaining devices continue; then apply mixed-result rule.
- Reopen: new occurrence + new deliveries (`delivery_generation=1`); old rows unchanged.

## 4. Queue fairness

Select `status IN ('pending','retry_scheduled')` AND (`next_retry_at IS NULL OR next_retry_at <= now`).  
Order: `next_retry_at ASC NULLS FIRST, created_at ASC`. Limit 50/shop/tick.  
`retry_scheduled` with future `next_retry_at` is skipped. Poisoned `failed_exhausted` is never re-selected. Older due work cannot be hidden by newer pending events.

## 5. Tables (canonical names)

All tables: `shop_id VARCHAR(36) NOT NULL` with composite FK `(shop_id) → shop(id)` **or** `(shop_id, id)` membership as used by identity. ON DELETE RESTRICT.

**notification_event**  
`id`, `shop_id`, `category`, `severity`, `title`, `body`, `action_url`, `dedupe_key`, `status`, `occurrence_seq` INT NOT NULL DEFAULT 1, `acknowledged_by`, `acknowledged_at`, `resolved_at`, `cancelled_at`, `created_at`, `updated_at`  
UNIQUE `(shop_id, id)`, UNIQUE `(shop_id, dedupe_key)`  
CHECK severity, status.

**notification_occurrence** (append-only)  
`id`, `shop_id`, `event_id`, `occurrence_seq`, `cause`, `created_at`  
UNIQUE `(shop_id, event_id, occurrence_seq)`  
FK `(shop_id, event_id) → notification_event(shop_id, id)`

**notification_delivery**  
`id`, `shop_id`, `event_id`, `occurrence_seq`, `subscription_id`, `delivery_generation` INT NOT NULL DEFAULT 1, `status`, `attempt_count`, `next_retry_at`, `attempted_at`, `error`, `created_at`  
UNIQUE `(shop_id, event_id, occurrence_seq, subscription_id, delivery_generation)`  
CHECK status IN (`pending`,`retry_scheduled`,`sent`,`failed_exhausted`,`expired`,`cancelled`)  
FK `(shop_id, event_id)`, `(shop_id, subscription_id)`  
Retry reuses this row. Reopen inserts new rows with new `occurrence_seq` and `delivery_generation=1`.

**notification_source** (durable intent index)  
`id`, `shop_id`, `source_kind`, `source_key`, `event_id`, `occurrence_seq`, `created_at`  
UNIQUE `(shop_id, source_kind, source_key)`  
FK `(shop_id, event_id)`. Recovery sweep uses this uniqueness so replay cannot duplicate occurrences.

**push_subscription**  
`id`, `shop_id`, `clerk_user_id`, `endpoint`, `p256dh`, `auth`, `enabled`, `failure_count`, `last_success_at`, `replaced_at`, `created_at`  
UNIQUE `(shop_id, endpoint)`

**notification_preference**  
`id`, `shop_id`, `clerk_user_id`, `web_push_enabled`, `action_required_enabled`, `critical_enabled` (shop-level critical disable is **not** this personal flag; see shop policy), quiet hours, timezone  
UNIQUE `(shop_id, clerk_user_id)`

**shop_notification_policy**  
`shop_id` PK, `critical_enabled` BOOL NOT NULL DEFAULT TRUE, `updated_at`  
Only owner may set `critical_enabled=false`.

**notification_audit** (append-only)  
`id`, `shop_id`, `actor_clerk_user_id`, `action` (`critical_disable|critical_enable|test_send|ack|resolve|cancel|reopen`), `category`, `prior_state`, `new_state`, `event_id` NULL, `created_at`  
No UPDATE/DELETE by runtime.

Indexes: `(shop_id, status, created_at)` on events; `(shop_id, next_retry_at, created_at)` on deliveries; `(shop_id, clerk_user_id)` on subscriptions.

Startup `create_all` on application Base **must not** create these tables. Migrator `apply_notification_schema()` one transaction, IF NOT EXISTS / skip existing, rerun no-op.

## 6. Worker

For each `Shop` row: try notification tick using `shop.id`; catch/rollback that session; continue. Tick **even if** auto-sync is skipped or Shopify pull failed. Inventory sync uses a separate session.

## 7. Durable intent vs transport

“After-commit emit” = **transport dispatch** after the durable business commit. The alert intent must already exist durably.

| Source | Pattern | Unique `source_kind` / `source_key` |
| --- | --- | --- |
| Inventory oversale | **B** — `inventory_exception` (kind oversale) is source of truth; sweep creates/recovers occurrence | `inventory_exception` / `{exception_id}` |
| Adjustment anomaly | **B** — `inventory_exception` kind `adjust_anomaly` is source of truth; sweep recovers | `inventory_exception` / `{exception_id}` |
| Card-resolution action-required | **B** if a durable review/exception row exists; else **A** outbox in the same txn as that durable card-resolution row | `card_resolution` / `{review_or_item_id}:{reason}` |
| Security/ops critical | **B** from durable security/ops event row; or **A** outbox in that row’s txn | `security` / `{security_event_id}` |
| Test send | **A** — the test `notification_event` **is** the durable record, inserted in the test request txn; transport after that commit | `test` / `{clerk_user_id}:{hour}` |

**A:** insert `notification_event` + `notification_source` (and occurrence) in the **same database transaction** as the durable business row. After COMMIT, worker/transport may send.  
**B:** business row is enough; sweep `WHERE eligible AND NOT EXISTS matching notification_source` inserts occurrence idempotently.

Crash after business commit, before notification insert: sweep repairs. Crash after notification insert, before send: delivery stays `pending`. Crash after provider success, before local `sent`: transport is at-least-once; a safe duplicate notification may be sent; unique `(shop_id, source_kind, source_key)` and delivery generation prevent a second occurrence; the extra provider send must not mutate inventory, adjustments, card-resolution, or security events; retry and outcome are audited. Exactly-once is not claimed. Transport errors do not roll back business rows. If notification tables are down, exception/adjust/sale status is unchanged (not marked resolved).

## 8. Identity

User routes: `get_notification_context` (JWT when issuer configured + membership).  
Test-send: authenticated member; rate-limit (e.g. 5/hour/user/shop).  
Critical disable: `role=owner` + confirmation flag required; write `notification_audit`.  
Staff: own subscription + noncritical prefs only.

## 9. Test send

`category='test'`, `dedupe_key` namespaced `test:{clerk_user_id}:{hour}`. Bypass quiet hours only. Does not share `dedupe_key` with real events. Cannot change real event status.

## 10. Web Push safety

HTTPS; explicit host allowlist; no URL userinfo; no redirects; block private/loopback/metadata IPs; resolve DNS on send. Payload: template title/body, relative `/admin/...` url, tag, eventId. Clicking the payload must not mutate inventory, exceptions, or workflow state. VAPID complete or send is a no-op.

## 11. Retention cleanup (later job, fail-closed)

Never delete unresolved critical events. Do not delete delivery rows < 90 days. Do not delete critical audit < 365 days. No cleanup while legal hold. Cleanup is a named job, not worker-tick side effect.

## 12. Compatibility

Identity slice: JWT + membership; headers untrusted.  
Inventory-truth 1.2.0: `shop_id` scoping; notification migrator separate from inventory-truth migrator; no `create_all` for either set of truth-like tables; adjustment/sale paths unchanged. Frontend out of scope.

## 13. Rollback

Flag off; unmount router; worker skips notification tick. Tables remain. Inventory schema untouched. Original worktree still holds source files.

## 14. Acceptance tests (backend)

Prior 28 tests plus: auto-sync off still ticks; shop A fail does not skip B; oldest due first under batch limit; mixed `sent`+`failed_exhausted` → occurrence delivered not pending; reopen preserves old deliveries; ack does not close inventory_exception; crash before business commit → no event; crash after commit before notification insert → sweep creates one occurrence; crash after insert before dispatch → one pending delivery; crash after provider success before local `sent` → uniqueness prevents a second occurrence and a possible safe duplicate push does not mutate business rows; notification DB failure does not resolve inventory_exception; owner-only critical disable + audit; staff cannot disable critical; test-send bypasses quiet hours and does not mutate real events; uniqueness conflict on same generation; migrator idempotent; create_all exclusion; no live network; duplicate payload/click is non-mutating.

## 15. Frozen files

Normative hashed bodies are listed only in
`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`.
This amendment, the directive, freeze-check evidence, and the 1.1.0
product-policy record do **not** store their own SHA-256. State, schema,
and test specifications in §2–§5 and §14 of this file are part of the
frozen amendment body.

Previous policy pointer: `docs/card-resolution-workflow/AMENDMENT-1.1.0.md`
(unchanged). Parent contract remains v1.0.0.

## 16. Frontend

Settings UI, service worker, auth hook, permission UX, install docs: **out of scope**. Backend may publish the payload contract in §10 for a later frontend slice.
