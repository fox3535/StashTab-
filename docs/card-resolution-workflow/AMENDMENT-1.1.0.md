# Proposed Contract Amendment 1.1.0 — Human-Intervention Notifications

**Parent contract:** `STASHTAB-CARD-RESOLUTION-001` version `1.0.0`  
**Status:** `PROPOSED — IMPLEMENTATION DISABLED BY DEFAULT`  
**Proposed:** `2026-08-14`  
**Human intent approval:** recorded in the project conversation on `2026-08-14`  
**Required before freeze:** independent architecture review, independent data-integrity review, acceptance evidence, and final human approval

## Change

Add tenant-scoped phone notifications for exceptions requiring human intervention. Routine successful processing remains automatic and does not require daily approval.

## Notification policy

| Severity | Examples | Default delivery |
|---|---|---|
| Routine | successful jobs, ordinary metrics | daily digest only |
| Action required | ambiguous card, unresolved printing/condition | immediate Web Push, deduplicated |
| Critical | reconciliation failure, tenant-scope violation, blocked pipeline | immediate Web Push; future email/SMS escalation if unacknowledged |

## Invariants

1. Notification records, subscriptions, preferences, queries, and delivery attempts are scoped by `shop_id`.
2. Lock-screen content contains no customer data, credentials, acquisition cost, or sensitive card details.
3. A notification links only to an authorized, tenant-scoped application route.
4. Repeated occurrences with the same active deduplication key update one event rather than spamming the user.
5. Delivery failure never changes the underlying workflow outcome or promotes an uncertain card.
6. Web Push is disabled unless a complete server-side VAPID configuration exists.
7. The VAPID private key never enters the browser bundle, logs, fixtures, or Git.
8. Users explicitly opt in per device and may disable a subscription.
9. Critical alerts cannot be disabled by non-owner roles once role enforcement is implemented.
10. Email/SMS fallback remains out of scope until its provider, consent, cost ceiling, and retention rules are approved.

## Required acceptance evidence

- Cross-tenant subscription, event, and acknowledgement access is rejected.
- Duplicate active events produce one notification event with an incremented occurrence count.
- Missing push configuration produces no external request.
- Expired subscriptions are disabled after a terminal provider response.
- Push payloads contain only title, generic body, safe application URL, tag, and event ID.
- iPhone Home Screen opt-in and Android/desktop opt-in are manually verified.
- Notification clicks open the authorized review destination.
- Delivery and acknowledgement are auditable.
- Existing card resolution and inventory tests remain green.

## Rollout

1. Merge tables, API, UI, and tests with delivery disabled.
2. Complete independent reviews and resolve findings.
3. Generate deployment-specific VAPID keys and configure staging only.
4. Validate opt-in, delivery, deduplication, tenant isolation, and deep links in staging.
5. Obtain final human approval and freeze contract version `1.1.0`.
6. Enable production Web Push. Add email/SMS only through a later amendment.
