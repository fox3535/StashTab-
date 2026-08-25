# DIRECTIVE — backend-notification-integration-v1

**Status:** `FROZEN — IMPLEMENTATION AWAITING NAMED UNLOCK`
**Approved amendment:** `STASHTAB-CARD-RESOLUTION-001 / AMENDMENT-1.1.1`
**Freeze manifest:** `docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`
This file does not store its own SHA-256.
**Target baseline:** `feature/inventory-truth-slice-03` @ `3a78278`
**Read-only source:** original worktree `checkpoint/inventory-truth-v1.1.0`
**Scope:** backend only. Frontend files stay deferred and unmodified.

Do not copy files, edit the original worktree, enable Web Push, migrate,
commit, or deploy from this packet.

## 1. Provenance map (read-only source)

Reusable as the starting design, not a drop-in:

| Source path (original tree) | Role |
| --- | --- |
| `services/api/app/models/notification.py` | Four tables: subscription, preference, event, delivery |
| `services/api/app/logic/notifications.py` | Create/dedupe, retry, process, generic copy |
| `services/api/app/logic/push_endpoints.py` | HTTPS, allowlist, no-redirect, private-IP deny |
| `services/api/app/routers/notifications.py` | HTTP API |
| `services/api/tests/test_notifications.py` | 28 passing tests, no live push |
| `services/api/app/deps.py` `get_notification_context` | JWT-required wrapper |
| `services/api/app/config.py` VAPID fields | `web_push_enabled` gate |
| `services/api/requirements.txt` `pywebpush` | Backend dependency |

Committed on the original checkpoint and **must be hand-reconciled** onto `3a78278`:

| Source | Target on `3a78278` |
| --- | --- |
| `services/api/app/main.py` | Restore router mount without dropping inventory routers |
| `services/api/worker.py` | Add notification tick **beside** per-shop isolation; never inside auto-sync skip |
| `services/api/app/deps.py` | Keep fail-closed shop context; keep notification JWT wrapper |
| `services/api/tests/test_identity.py` | Restore notification stubs without undoing identity assertions |
| CI / requirements | Add `pywebpush` if missing on slice-03 |

Deferred (do not integrate now):

- `components/notification-settings.tsx`
- `hooks/use-api-auth.ts`
- `public/sw.js`
- `app/admin/settings/page.tsx` notification UI
- Other modified admin/POS pages and `scripts/run_cursor_review.mjs`

## 2. Target integration file map (`3a78278`)

Add (adapted, not blind copy):

- `services/api/app/models/notification.py`
- `services/api/app/logic/notifications.py`
- `services/api/app/logic/push_endpoints.py`
- `services/api/app/routers/notifications.py`
- `services/api/tests/test_notifications.py`
- `services/api/app/notifications_truth/migrator.py` **or** an Alembic revision owned by API, **not** `init_db()`/`create_all` column hacking

Edit by hand:

- `services/api/app/main.py` — include router
- `services/api/worker.py` — isolated notification tick per shop, independent of Shopify auto-sync
- `services/api/app/deps.py` — JWT notification context
- `services/api/tests/test_identity.py`
- `services/api/app/models/__init__.py` — export models for mapper, **not** for `create_all` of truth-like audit tables if those are migrator-owned
- CI workflow to run `test_notifications.py`

Do not touch inventory_truth migrator tables or frozen contract bodies.

## 3. Contract / amendment requirement

`docs/card-resolution-workflow/AMENDMENT-1.1.0.md` is **PROPOSED, not frozen**. It is still the right **product policy** (shop-scoped records, generic lock-screen copy, VAPID-off default, delivery must not change workflow outcome).

It is **not sufficient** as the backend integration contract. It does not specify: migrator-only schema, worker isolation, per-device terminal states, queue fairness, reopen-without-delete, inventory-transaction isolation, or append-only delivery audit.

**Decision recorded in this plan:** do **not** silently edit 1.1.0. Create a **versioned correction** `AMENDMENT-1.1.1` (new file) that keeps 1.1.0 policy and adds backend mechanics. Human freeze is of 1.1.1 + this DIRECTIVE, not a rewrite of 1.1.0.

## 4. Binding resolutions (the 20 items)

1. **Auth.** Notification user routes use `get_notification_context`: verified JWT (or approved local bypass) **and** shop membership. `X-Shop-Id` / `X-Clerk-User-Id` are never authentication.
2. **Jobs.** Worker uses `Shop.id` from the database. No request headers.
3. **Auto-sync.** Notification tick runs even when `_shop_auto_sync` is false. Shopify pull failure must not skip notifications.
4. **Isolation.** Each shop’s notification tick is try/except + rollback of **that** session. One shop cannot stop the loop or other shops.
5. **Retry fairness.** Due deliveries ordered by `next_retry_at ASC NULLS FIRST, created_at ASC`, cap N per shop per tick. Failed rows get bounded exponential backoff. Newer due rows are not blocked by a poisoned old row: skip rows whose `next_retry_at` is in the future; never `ORDER BY created_at DESC` as the only cursor.
6. **Per-device terminal.** Unique `(shop_id, event_id, occurrence_seq, subscription_id, delivery_generation)`. States: `pending`, `retry_scheduled`, `sent`, `failed_exhausted`, `expired`, `cancelled`. One device `sent` and another `failed_exhausted`: occurrence `delivered` if any `sent` and none still `pending`/`retry_scheduled`. Zero devices: occurrence `failed`.
7. **Reopen.** New genuine occurrence (same `dedupe_key` after ack/resolve/cancel/fail) sets event back to `pending`, increments `occurrence_count`, writes an **append-only occurrence/audit row**, and creates **new** delivery rows (or a new `delivery_generation`). **Do not DELETE** prior deliveries.
8. **Shop-bound devices.** Every delivery and subscription row has `shop_id`. Composite uniqueness includes `shop_id`. Cross-shop FKs rejected.
9. **Races.** Dedupe via unique `(shop_id, dedupe_key)` + IntegrityError retry. Drop process-local lock maps as the source of truth. Test-send and worker serialize on the delivery unique key.
10. **Endpoints.** HTTPS only, explicit host allowlist, no credentials in URL, no redirects, block loopback/link-local/metadata IPs; DNS resolve on the actual HTTP send (`resolve_dns=True`).
11. **Payload.** Title/body from server templates only. `action_url` is a relative `/admin/...` path generated or allowlisted by the server. No customer, cost, or PAN data.
12. **VAPID.** `web_push_enabled` is false unless public key, private key, and `mailto:`/`https:` subject exist. No send, no external HTTP.
13. **Durable intent.** Transport starts after business commit. Critical sources use AMENDMENT-1.1.1 §7: oversale/adjust_anomaly sweep from `inventory_exception`; card-resolution and security from durable source row or same-txn outbox; test-send’s notification row is the durable record. Crash after commit cannot permanently lose the alert. Sweep uniqueness `(shop_id, source_kind, source_key)` prevents duplicate occurrences. Transport failure never rolls back inventory. Notification-table outage cannot resolve exceptions. Transport is at-least-once (D-N5): a crash after provider success before local `sent` may send a safe duplicate; payloads and clicks are non-mutating; exactly-once is not claimed.
14. **Ack ≠ resolve exception.** Acknowledge/resolve notification APIs update notification rows only. They must not call inventory exception resolution.
15. **Backlog.** Cursor is due-time, not “newest 100”. Rows with future `next_retry_at` are skipped, not selected as the whole batch.
16. **Migration.** Notification tables are created/altered only by a controlled, idempotent migrator (same discipline as inventory-truth: one transaction, rerun no-op, `create_all` on app Base does not own these tables **or**, if they stay on app Base for SQLite tests, production Postgres apply is still migrator-only and startup `_ensure_columns` is **not** the lifecycle). No startup ALTER list for notification schema.
17. **Runtime role.** Queries always filter `shop_id` from verified context or persisted Shop.id. Delivery/event history: no silent overwrite of sent audit; updates limited to retry-state columns on non-terminal deliveries. Optional later: append-only trigger on a `notification_audit` table.
18. **Schema (explicit).** See §6.
19. **Tests.** No live VAPID, no real endpoints; mock `webpush`; fixtures only.
20. **Closed path.** See §13.

## 5. State machine

Canonical event, occurrence, and per-device states are AMENDMENT-1.1.1
§2–§3. Delivery statuses: `pending`, `retry_scheduled`, `sent`,
`failed_exhausted`, `expired`, `cancelled`. Terminal: last four.

Owners:

- Durable intent: same-txn outbox (pattern A) or recovery sweep from a
  durable business row (pattern B)
- Transport: worker, after commit only
- Acknowledge/resolve: authenticated member (notification rows only)
- Cancel: owner

Evidence: event + occurrence + delivery + `notification_source` + audit.
Attempt limit 8. Mixed `sent` + `failed_exhausted` with nothing in-flight
→ occurrence `delivered`. Transport is at-least-once (D-N5).

## 6. Database / migration model

Canonical names and uniqueness: AMENDMENT-1.1.1 §5.
Required: `notification_event`, `notification_occurrence`,
`notification_delivery`, `notification_source`, `push_subscription`,
`notification_preference`, `shop_notification_policy`,
`notification_audit`. Unique source key `(shop_id, source_kind,
source_key)`. Unique delivery
`(shop_id, event_id, occurrence_seq, subscription_id, delivery_generation)`.

Retention: AMENDMENT-1.1.1 clause 22. Cleanup is a later named job; first
slice **does not auto-delete**.

Migrator: `apply_notification_schema()` in one transaction, idempotent,
fail-closed. Tests prove `create_all` on a stripped metadata cannot be the
production path. Separate from the inventory-truth migrator.

## 7. Retry and queue fairness

- Max attempts: 8
- Backoff: `min(3600, 30 * 2^(attempt-1))` seconds
- Select: `pending` or due `retry_scheduled`, oldest-due first, limit 50
  per shop per tick
- Poison: `failed_exhausted` is never re-selected
- Newer alerts cannot hide older due work
- Retry and transport outcome are audited (D-N5)

## 8. Identity / authorization matrix

| Action | JWT + membership | Shop.id job | Headers as auth |
| --- | --- | --- | --- |
| GET config (public vapid if enabled) | optional | n/a | no |
| Preferences / subscribe / ack / resolve / test | required | no | no |
| process_pending | no HTTP | yes | no |
| Cross-shop event id | 404 | n/a | n/a |

Critical preference: non-owner cannot disable critical (1.1.0 item 9) — **implement in this backend slice** as a closed rule: owner-only to set `critical_enabled=false`.

## 9. Backend API and safe payload

Keep existing routes under `/api/v1/notifications`. Payloads:

```
title, body  // server templates only
url          // relative /admin/...
tag          // dedupe_key
eventId      // uuid
```

No inventory quantities, SKUs of customer deals, or names.

Handoff to frontend (later): subscribe with JWT; display VAPID public only when enabled; click opens `url`.

## 10. Worker isolation

```
for shop in Shop.all():
    try: maybe_sync(shop)   # skip if auto-sync off
    except: log; continue
    try: process_pending_notifications(shop.id)
    except: rollback notif session; continue
```

Notification session ≠ inventory session.

## 11. Acceptance-test matrix (backend)

Existing 28 tests remain, plus:

- Auto-sync off still delivers
- Shop A throw does not skip shop B
- Oldest due processed before newer when batch-limited
- Mixed device sent+exhausted → event not pending
- Reopen does not delete old deliveries
- Ack does not close `inventory_exception`
- Crash before commit / after commit / before dispatch / after provider success: see AMENDMENT-1.1.1 §14
- create_notification after inventory commit: inventory persists if push mocked to fail
- Migrator idempotent; create_all does not add notification columns on a stub Base
- No live network (patch webpush and DNS)

## 12. Rollback

Feature flag `NOTIFICATIONS_BACKEND_ENABLED` default false until unlock. Router unmounted if flag off. Tables may remain empty. No inventory schema rollback. Original worktree still holds source files.

## 13. Closed planning path

| State | Owner | Evidence | Attempts | Terminal |
| --- | --- | --- | --- | --- |
| PLANNING | planner | this DIRECTIVE + reviews | 1 correction | → READY_FOR_FREEZE_CHECK |
| FREEZE_CHECK | reviewer ≠ planner | 20 items + amendment 1.1.1 | 1 | FROZEN or REJECTED |
| implementation_unlock | human | freeze record | 1 | backend slice may start |
| Integration merge | human | both test suites green | 1 | merge or stop |

Timeout is not success.

## 14. Smallest backend integration slice

One unlock: schema migrator + adapted models/logic/router/worker mounts + identity test repair + notification tests, Web Push still off without VAPID, no frontend.

## 15. Genuine human decisions

Closed 2026-08-24: D-N1 retention; D-N2 owner-only critical disable with audit;
D-N3 uniqueness `(shop, occurrence, subscription, delivery_generation)`;
D-N4 test-send quiet-hours bypass; D-N5 at-least-once transport with
idempotent non-mutating payloads. Remaining blocker is the named
implementation unlock. Do not implement from this freeze action.
