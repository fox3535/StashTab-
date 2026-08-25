# Kickoff review — card-resolution human notifications

**Date:** 2026-08-14  
**Branch:** `feature/card-resolution-notifications` (uncommitted working tree; no local commit)  
**Contract:** frozen `STASHTAB-CARD-RESOLUTION-001` `1.0.0` plus proposed amendment `1.1.0`  
**Status:** not freeze-ready; human approval required before implementation fixes, commit, or push

This record synthesizes three independent local reviews of the same uncommitted diff. Agreement is not acceptance evidence.

| Role | Reviewer |
|---|---|
| Architecture | [Architecture review](a94d7f53-ee24-4e40-9468-8d3f5b542f0b) |
| Data integrity | [Data-integrity review](451ef11c-570c-46b9-a5a8-1ae0043a4063) |
| Security | [Security review](76cc8ed8-d5ea-47e3-8e91-3df95cac4950) |

GitHub cross-platform review (`.github/workflows/cross-platform-review.yml`) is present but has not run. This document is the local kickoff synthesis only.

---

## Shared conclusions

- FastAPI still owns notification business logic. Next.js is a thin client plus required browser pieces.
- Queries that already have shop context are `shop_id`-scoped. Cross-tenant *query* leaks were not demonstrated once context is set.
- Web Push stays off unless VAPID public key, private key, and subject are all truthy. No known CVE was cited for `pywebpush>=2.0.3`; the risk is how endpoints are used.
- Delivery code does not write intake, staging, or inventory in this diff, so amendment invariant 5 currently holds.
- Removing authenticated `X-Shop-Id` fallback in `services/api/app/deps.py` is a tenant-isolation improvement, not a regression.
- Amendment invariant 9 (critical alerts locked for non-owners) is explicitly deferred.
- Missing Alembic is the existing `create_all` pattern, not a new unauthorized migration system. Later unique-index *changes* will not be applied by `create_all`.

---

## Ranked corrections

Duplicate findings are grouped. Severity is the highest assigned by any reviewer. Disagreements are recorded under each item.

### P1-A — Failed deliveries never retry and can stall the queue

**Reviewers:** architecture, data integrity, security (security as process gap; others as P1)

| Field | Detail |
|---|---|
| **Severity** | P1 |
| **File / line** | `services/api/app/logic/notifications.py` 75–78, 95–100, 129–138; `services/api/app/models/notification.py` 62–64 |
| **Clauses** | Amendment invariants 4–5; frozen §8 (failures stay retryable); amendment evidence on expired subscriptions and auditable delivery; frozen §11 reconciliation |
| **Evidence** | Any delivery row for `(event_id, subscription_id)` causes skip, including `failed`. Unique constraint blocks a second row. Transient 429/500 treated like 404/410. Event stays `pending` if all fail, or becomes `delivered` if any succeed. Pending load is `.limit(100)` with no order. |
| **Failure** | Provider 500s leave dead-letter pending events. A backlog of 100 stuck rows can starve newer alerts. One device succeeds and another 503s: event looks delivered; staff never retried. |
| **Correction** | Retry non-terminal failures by updating the existing delivery row with backoff. Disable only on 404/410. Order pending events. Cap/defer so failed rows leave the hot batch. Mark event delivered only when every eligible target is sent, expired, or opted out. |
| **Acceptance test** | 503 then success → one delivery row updated to `sent`. 410 → subscription disabled, no further attempts. 101 failed pending plus one new event → new event still processed. Two subscriptions, one success and one 503 → failed target retries. |

**Disagreement:** Security treated this as a compliance gap, not a standalone exploit. Architecture and data integrity treat it as a P1 lifecycle defect. Synthesis keeps P1 because action-required/critical alerts would silently die once VAPID is enabled.

---

### P1-B — Dedupe unique key plus acknowledgement hides later alerts

**Reviewers:** architecture, data integrity (both P1)

| Field | Detail |
|---|---|
| **Severity** | P1 |
| **File / line** | `services/api/app/logic/notifications.py` 30–53; `services/api/app/routers/notifications.py` 107–132; `services/api/app/models/notification.py` 42–44, 53–57 |
| **Clauses** | Amendment invariant 4 (active key); frozen §3.8 idempotency; amendment evidence on duplicate active events and auditable ack |
| **Evidence** | Unique `(shop_id, dedupe_key)` is forever. Increments occur unless status is `resolved`/`cancelled`. Nothing writes those statuses or `resolved_at`. Acknowledge sets `acknowledged`. After send, status is `delivered`. Later creates bump `occurrence_count` and body but do not return to `pending`. `list_events` only returns pending/delivered. |
| **Failure** | User acknowledges an ambiguous-card alert. Same key fires again: count increments, list hides it, no push. A future resolve insert hits `IntegrityError`. |
| **Correction** | Partial unique index on active statuses, or reopen the row to `pending` on new occurrence after ack/resolve. Add an explicit resolve/cancel write. Do not insert a second row while the unconstrained unique still exists. |
| **Acceptance test** | Sequential duplicate creates → one row, count 2. After acknowledge, same key → new visible pending event or reopened row and a new delivery attempt. After resolve, same key inserts without integrity error; old row stays resolved. |

---

### P1-C — Concurrent event inserts are not idempotent

**Reviewers:** data integrity (P1). Architecture did not list this separately.

| Field | Detail |
|---|---|
| **Severity** | P1 |
| **File / line** | `services/api/app/logic/notifications.py` 30–53 |
| **Clauses** | Amendment invariant 4; frozen §3.8 |
| **Evidence** | Lookup has no row lock. Occurrence increment is Python read-modify-write. No `IntegrityError` handler. Tests only cover sequential creates. |
| **Failure** | Two workers emit the same key; one request 500s; count can be lost. |
| **Correction** | Catch unique violation and increment, or `SELECT … FOR UPDATE`, or SQL `occurrence_count = occurrence_count + 1`. |
| **Acceptance test** | Two concurrent `create_notification` calls → exactly one row, count 2, no unhandled integrity error. |

---

### P1-D — Background delivery is skipped when Shopify auto-sync is off

**Reviewers:** all three (architecture/data P1; security medium)

| Field | Detail |
|---|---|
| **Severity** | P1 |
| **File / line** | `services/api/worker.py` 33–43 |
| **Clauses** | Amendment policy table (immediate push for action-required/critical); frozen §8 and §14; amendment invariant 5 (do not couple delivery to other workflows) |
| **Evidence** | Shop loop `continue`s on `auto_sync_enabled=false` before `process_pending_notifications`. `/notifications/test` can still send. |
| **Failure** | Shop disables Shopify auto-sync. Human-review and reconciliation alerts stay pending forever even with VAPID and devices. |
| **Correction** | Process notifications for every shop, independent of auto-sync. |
| **Acceptance test** | Shop with auto-sync off, VAPID on, pending action-required event, enabled subscription → delivery attempted and recorded. |

---

### P1-E — Lock-screen text and click URLs are not enforced

**Reviewers:** all three (architecture P1; security/data medium/P2)

| Field | Detail |
|---|---|
| **Severity** | P1 |
| **File / line** | `services/api/app/logic/notifications.py` 19–28, 107–113; `services/api/app/models/notification.py` 49–51; `public/sw.js` 1–23 |
| **Clauses** | Amendment invariants 2–3; evidence “payloads contain only title, generic body, safe application URL, tag, and event ID” |
| **Evidence** | Caller `title`/`body`/`action_url` stored and pushed verbatim. No template or allowlist. Service worker `new URL(url, origin)` keeps absolute `https://evil.example` and protocol-relative `//evil`. Card-resolution callers are not wired yet; test copy is currently safe. |
| **Failure** | Future intake passes card name, cost, or customer text onto the lock screen. Click opens an off-site page. |
| **Correction** | Server templates per severity/category. Allow only relative `/admin/...` paths. Service worker must reject off-origin URLs. |
| **Acceptance test** | Body with cost/card/customer identifiers is rejected or replaced in the push payload. `https://evil.example` and `//evil` rejected. Click handler only opens a same-origin admin path. |

**Disagreement:** Security and data integrity rated this medium/P2 because no card-resolution caller exists yet. Architecture rated P1 because the contract requires enforcement at the push boundary before freeze. Synthesis keeps P1: freeze of 1.1.0 would certify a hole that later callers will hit.

---

### P1-F — Settings UI never sends Clerk identity; unauthenticated shop access

**Reviewers:** architecture P1; security HIGH (auth + shared actor). Data integrity: not a data-model leak; `deps.py` change is a tightening.

| Field | Detail |
|---|---|
| **Severity** | P1 (security HIGH for unauthenticated `X-Shop-Id` on new surfaces) |
| **File / line** | `components/notification-settings.tsx` 43–50, 70, 86, 100, 136; `lib/admin-api.ts` `adminFetch`; `services/api/app/deps.py` 43–48; `services/api/app/auth/clerk.py` 45–46; `services/api/app/logic/notifications.py` 15–16; `services/api/app/routers/notifications.py` 31–32, 45–91 |
| **Clauses** | Frozen invariant 1; amendment invariants 1 and 8; amendment evidence “cross-tenant subscription, event, and acknowledgement access is rejected” |
| **Evidence** | Notification settings call the API without Clerk token. Inventory already passes tokens. Unauthenticated requests bind tenant via `X-Shop-Id`. `X-Clerk-User-Id` is accepted without JWT when no verified bearer is present. Missing clerk id stores `dev:{shop_id}` for preferences, subscriptions, and test dedupe. |
| **Failure** | Anyone who knows/guesses a shop id can register endpoints, change prefs, list/ack events, and trigger `/notifications/test`. Staff in one shop overwrite one shared actor. Rows will not match real users when Clerk is wired. |
| **Correction** | Pass Clerk auth from notification settings. Require verified JWT on mutating and per-user notification routes when Clerk is configured. Do not issue `dev:` actors in that mode. Reject unauthenticated `X-Shop-Id` outside explicit local dev. |
| **Acceptance test** | Subscribe/prefs/events/ack/test without Bearer return 401/403 when Clerk is on. Two members keep isolated preferences. Cross-shop `X-Shop-Id` with another user’s JWT cannot access foreign data. |

**Disagreement:** Data integrity would not call unauthenticated `GET /notifications/config` a defect (VAPID public key is meant to be public). Architecture/security agree on the actor collapse. Synthesis: public config may stay unauthenticated; mutating routes and per-user reads must not.

---

### P1-G — CI can pass without amendment acceptance evidence

**Reviewers:** architecture P1; security/data as process gaps

| Field | Detail |
|---|---|
| **Severity** | P1 |
| **File / line** | `.github/workflows/card-resolution-gates.yml` 3–15, 33–35; `scripts/validate_card_resolution_contract.py` 7–16; `services/api/tests/test_notifications.py` |
| **Clauses** | Amendment required acceptance evidence; frozen §13 and §15 |
| **Evidence** | Path filter omits `scripts/**` and root `.env.example`. Validator only checks markdown phrases. Tests cover sequential in-shop dedupe and cross-shop *create* isolation only. No HTTP tenant-reject, no mocked missing-VAPID “no outbound call”, no 410, no payload rules, no ack. |
| **Failure** | Green “contract gates” while most 1.1.0 acceptance bullets are unproven. |
| **Correction** | Run gates when scripts, env examples, and workflow change. API tests with mocked `webpush` covering the amendment list. Guard committed files against `NEXT_PUBLIC_*VAPID*PRIVATE*`. |
| **Acceptance test** | The amendment’s acceptance bullets, plus CI running when the validator script changes. |

---

### P1-H — Server-side SSRF via attacker-controlled push endpoints

**Reviewers:** security HIGH. Architecture/data did not list SSRF as a named finding.

| Field | Detail |
|---|---|
| **Severity** | P1 (security HIGH) |
| **File / line** | `services/api/app/routers/notifications.py` 15–18, 75–91, 136–145; `services/api/app/logic/notifications.py` 115–123 |
| **Clauses** | Amendment invariant 1; frozen §3.10 (unsafe external side effects) |
| **Evidence** | `endpoint` is length-checked only. Stored URL is passed to `pywebpush` with no scheme/host allowlist. Combined with P1-F, unauthenticated callers can trigger outbound POSTs via `/notifications/test` or the worker. |
| **Failure** | Register `http://127.0.0.1/` or cloud metadata as a “subscription”; worker or test endpoint probes internal services. |
| **Correction** | Allowlist HTTPS push-provider hosts; reject others before any outbound HTTP; disable redirects. |
| **Acceptance test** | Shop member cannot register loopback/metadata URLs; no outbound HTTP; legitimate FCM/Mozilla/Apple endpoints still accepted. |

**Disagreement:** Architecture/data focused on lifecycle and constraints, not SSRF. Synthesis keeps P1 because it is a real attack path once any caller can establish shop context, and P1-F makes that easy.

---

### P2-A — Push is sent before the delivery row is committed

**Reviewers:** architecture, data integrity

| Field | Detail |
|---|---|
| **Severity** | P2 |
| **File / line** | `services/api/app/logic/notifications.py` 101–139 |
| **Clauses** | Frozen §8 and §10; amendment invariant 5; auditable delivery |
| **Evidence** | `webpush` runs in the loop; one `db.commit()` after the shop batch. Crash or unexpected exception rolls back `sent` rows after the provider already accepted. Worker and `/test` can race the unique delivery key. |
| **Failure** | Duplicate push; or one error undoes other recorded sends. |
| **Correction** | Persist attempt row (or savepoint) before the network call; update after. Catch unique violations as no-op. Catch non-`WebPushException` per target. Do not share a dirty session with Shopify sync. |
| **Acceptance test** | Success then generic exception before commit → at most one extra send after recovery, audit row exists. Concurrent worker + test → one delivery row per `(event, subscription)`. |

---

### P2-B — Notification helpers commit the caller’s session

**Reviewers:** architecture P2. Data integrity: not a current workflow-outcome defect; will become a transaction-split bug if intake calls `create_notification` in the same session.

| Field | Detail |
|---|---|
| **Severity** | P2 |
| **File / line** | `services/api/app/logic/notifications.py` 38, 51, 139 |
| **Clauses** | Frozen §10; amendment invariant 5 |
| **Evidence** | `create_notification` and `process_pending_notifications` call `db.commit()`. |
| **Failure** | Future intake adds inventory then notifies in one session; notification commit writes inventory even if the rest fails. |
| **Correction** | Add/flush only, or use a separate session if notifications must survive workflow rollback. |
| **Acceptance test** | Create notification inside an uncommitted inventory transaction, roll back, assert neither row remains. |

**Disagreement preserved:** Data integrity says invariant 5 is satisfied *in this diff* because notifications are not wired into intake. Architecture wants the helper fixed before that wiring. Synthesis: fix before any card-resolution caller uses the helper.

---

### P2-C — Delivery uniqueness and FKs are not shop-bound

**Reviewers:** data integrity P2

| Field | Detail |
|---|---|
| **Severity** | P2 |
| **File / line** | `services/api/app/models/notification.py` 60–68; `services/api/app/logic/notifications.py` 95–98; `services/api/app/models/base.py` 20–23 |
| **Clauses** | Amendment invariant 1; frozen §3.1 |
| **Evidence** | Unique key and existence query omit `shop_id`. FKs are to parent ids only. `shop_id` is indexed, not a FK to `shops`. Current pairing loop does filter parents by shop. |
| **Failure** | Manual/bug write can attach shop A delivery to shop B’s event. |
| **Correction** | Include `shop_id` on every delivery lookup; composite unique/FKs or a check that parent shop matches. |
| **Acceptance test** | Cross-shop event/subscription ids must not match. Mismatched `shop_id` insert must fail. |

---

### P2-D — Preference/subscription upserts can 500; in-shop endpoint takeover

**Reviewers:** data integrity P2; security medium (takeover)

| Field | Detail |
|---|---|
| **Severity** | P2 |
| **File / line** | `services/api/app/routers/notifications.py` 62–90, 96–100; `services/api/app/models/notification.py` 11, 25–27 |
| **Clauses** | Amendment invariants 1 and 8; frozen §3.8 |
| **Evidence** | Query-then-insert without integrity handling. POST overwrites `clerk_user_id` on endpoint collision; DELETE requires matching owner. |
| **Failure** | Double-click Enable → 500. Staff B POSTs Staff A’s endpoint and inherits the device. |
| **Correction** | Idempotent upsert. On endpoint collision, 409 unless same owner or prior DELETE. |
| **Acceptance test** | Concurrent POSTs of one endpoint → one row, no 500. User B posting User A’s endpoint → 403/409. Concurrent preference PUTs → one row, last write wins. |

---

### P2-E — Root env example names the VAPID private key for Next.js

**Reviewers:** architecture P2

| Field | Detail |
|---|---|
| **Severity** | P2 |
| **File / line** | `.env.example` 23–27 (and header instructing copy to Next.js `.env.local`) |
| **Clauses** | Amendment invariants 6–7 |
| **Evidence** | Empty placeholders are not a Git leak. Operators who fill the Next.js env file still place the private key in the Next process. Subject defaults to `mailto:ops@example.com`, so filling only the two keys enables `web_push_enabled`. |
| **Failure** | Staging private key lands in Next.js env. Unintentional enablement if keys are set without a conscious subject. |
| **Correction** | Keep VAPID keys only in `services/api/.env.example`. Do not name the private key in the Next.js example. Require a non-default subject, or an explicit enable flag, before `web_push_enabled`. |
| **Acceptance test** | No `NEXT_PUBLIC_*VAPID*PRIVATE*` in committed files. Next.js env example does not include the private key. Empty/default subject does not enable push. |

---

### P3 — Unused digest/quiet-hours and unconstrained enums

**Reviewers:** architecture P3 (unused prefs); data integrity P3 (free strings)

| Field | Detail |
|---|---|
| **Severity** | P3 |
| **File / line** | `components/notification-settings.tsx` 125–134; `services/api/app/logic/notifications.py` 56–63; `services/api/app/models/notification.py` 34–37, 48–53, 70 |
| **Clauses** | Amendment policy table; frozen §8 |
| **Evidence** | Daily digest and quiet hours are saved and never read. Unknown severity never sends but stays pending. Invalid status never matches worker/list filters. |
| **Failure** | User believes quiet hours work. `severity="action-required"` never delivers. |
| **Correction** | Hide unused controls or implement them in FastAPI. Check constraints/enums for severity and status. Do not enqueue routine events as immediate pending pushes. |
| **Acceptance test** | Unknown severity/status rejected at write. Routine events never call `webpush`. Quiet hours, if kept, suppress push in-window. |

---

## Intentionally not treated as defects

| Topic | Position |
|---|---|
| Default-disabled Web Push | All three: genuine. Residual: default `vapid_subject` means two keys are enough. |
| VAPID private key in API config / public key on `/config` | Intended. Public key may stay public. |
| `deps.py` membership requirement for JWT users | Hardening. Multi-shop `.first()` membership predates this branch. |
| Critical-alert role lock | Deferred by invariant 9. |
| No Alembic | Existing `create_all` will create the four new tables. Human approval still required before production schema apply (frozen §12.8). |
| pywebpush CVE | None identified. Architectural SSRF remains. |
| Email/SMS | Out of scope (invariant 10). |
| Delivery failure promoting cards | Not in this diff. Becomes real if `create_notification` is called inside intake transactions without fixing P2-B. |

---

## Proposed correction plan (for human approval)

Do not enable VAPID, migrate production, commit, or push until this plan is approved.

1. **Auth and actor (P1-F, P1-H, P2-D)**  
   Wire Clerk tokens on notification settings. Require JWT when Clerk is configured. Allowlist push endpoints. Idempotent upserts; no silent endpoint takeover.

2. **Delivery state machine (P1-A, P2-A, P2-C)**  
   Per-target retry, terminal vs retryable errors, shop-scoped delivery constraints, persist attempt before provider call.

3. **Dedupe lifecycle (P1-B, P1-C)**  
   Active-only uniqueness, reopen or new generation after ack/resolve, concurrent-safe increment, explicit resolve path.

4. **Worker isolation (P1-D)**  
   Drain notifications even when Shopify auto-sync is off.

5. **Lock-screen and deep links (P1-E)**  
   Generic templates, relative `/admin` allowlist, same-origin service worker.

6. **Session ownership (P2-B)**  
   Stop committing inside helpers before any card-resolution caller.

7. **Secrets and enablement (P2-E)**  
   Remove private key from Next.js env example. Do not treat default subject as complete VAPID config.

8. **Acceptance tests and CI (P1-G, P3 as needed)**  
   Cover the amendment evidence list with mocked provider calls. Fix gate path filters.

9. **After fixes**  
   Re-run independent architecture, data-integrity, and security review. Then GitHub cross-platform review on a PR. Human freeze of 1.1.0 still required before staging VAPID, and again before production delivery.

---

## Stop line

No implementation files were changed for this synthesis. Next step is human approval of the correction plan.
