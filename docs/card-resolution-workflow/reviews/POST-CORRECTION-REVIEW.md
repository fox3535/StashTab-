# Post-correction review synthesis

**Date:** 2026-08-14  
**Branch:** `feature/card-resolution-notifications` (uncommitted)  
**Contract:** frozen `1.0.0`; amendment `1.1.0` remains proposed  
**Status:** not freeze-ready

Independent re-reviews of the corrected working tree:

| Role | Reviewer |
|---|---|
| Architecture | [Architecture review](d1774f48-ada1-452e-87b3-22178088719f) |
| Data integrity | [Data-integrity review](c0a0908b-2d95-4cd2-8c29-0060c3652ad0) |
| Security | [Security review](77fcd672-afc9-485c-8a2b-689637aa2a24) |
| Adversarial | [Adversarial review](52461c9e-7193-4b0a-824a-1debb05878e5) |

Agreement is not acceptance evidence.

---

## Closed from kickoff (all four)

- Auth when Clerk JWT is configured; settings UI sends tokens; shop-id alone is not enough on notification routes
- HTTPS push endpoints with private/loopback/metadata rejection, provider suffixes, no redirects
- Generic lock-screen copy and same-origin `/admin` click URLs
- VAPID default-off, including placeholder subject; private key not in Next.js env example
- Tenant-scoped queries; cross-shop ack 404; subscription 409 unless prior owner disabled
- Dedupe reopen after ack/resolve; worker drain when auto-sync is off
- `create_notification` does not commit the caller session
- Automated amendment tests and CI path coverage for scripts/env examples

Not reproduced: cross-tenant reads/writes, default-host SSRF, lock-screen PII, off-site clicks, forced delivery enablement, duplicate inventory.

---

## Remaining findings (grouped)

### P1-1 — Mixed success and exhausted failure leaves events pending

**Reviewers:** architecture, data integrity (both P1)

If one device is `sent` and another hits max retries as `failed`, the event stays `pending` and can occupy the hot batch. Same stall class as original P1-A.

**Correction:** Treat exhausted failures as terminal. If any target sent and the rest are expired/exhausted → `delivered`. If none sent → `failed`. Do not record exhausted rows as `retry`.

**Test:** Two subscriptions, max attempts 1, one success and one 503 → event leaves `pending`; a newer event still processes.

---

### P1-2 — Shopify sync crash skips other shops and can kill the worker

**Reviewers:** architecture P2; adversarial P1 (synthesis keeps P1)

`run_full_sync` is uncaught. A throw skips that shop’s notification drain, later shops in the same tick, and can exit the worker.

**Correction:** Isolate sync in try/except. Always drain notifications. Catch per shop in the main loop.

**Test:** Shop A sync raises; shop B auto-sync off with a pending alert → B is still processed and the loop continues.

---

### P2 — Other residuals

| Item | Reviewers | Correction |
|---|---|---|
| Unverified `X-Clerk-User-Id` when JWT issuer is unset | security medium | Fail closed on notification routes unless issuer is set, or an explicit local-dev flag |
| 100 newest undeliverable pending rows hide older due events | adversarial P2 | Select due events, or skip not-due rows so they do not fill the batch |
| Reopen wipes ack and delivery history | architecture, data integrity | Keep prior ack/delivery rows (generation or audit copy) |
| Delivery FKs not shop-bound | architecture, data integrity | Composite FKs or DB check that parent shop matches |
| Concurrent worker + `/test` can double-send | architecture, data integrity | Lock/CAS delivery row before provider call |
| Cross-process occurrence increment can be lost | architecture, data integrity | SQL `occurrence_count = occurrence_count + 1` |
| `create_all` will not alter existing local notification tables | data integrity | Ensure-columns or require a wiped local DB |

Invariant 9 (critical alerts locked for non-owners) remains deferred.

---

## Proposed next corrections (needs human approval)

1. Close P1-1 (terminalize mixed exhausted deliveries) and add the mixed max-attempt test.
2. Close P1-2 (sync failures must not skip notification drain or abort other shops).
3. Address P2 items that remain relevant before any card-resolution caller or VAPID enablement, especially Clerk fail-closed, due-event selection, and audit-preserving reopen.

Do not freeze 1.1.0, enable VAPID, migrate production, commit, or push until these are fixed or explicitly accepted.

---

## Stop line

No implementation files were changed for this synthesis. Next step is human approval of the remaining correction list.
