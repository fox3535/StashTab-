# Correction evidence — notification checkpoint

**Date:** 2026-08-14  
**Branch:** `feature/card-resolution-notifications` (still uncommitted)  
**Starting point:** `docs/card-resolution-workflow/reviews/KICKOFF-REVIEW.md` (approved)  
**Contract:** frozen `1.0.0`; amendment `1.1.0` remains proposed and not frozen  
**Web Push:** still disabled by default (empty VAPID subject does not enable; placeholder `mailto:ops@example.com` does not enable)

## Tests run

- `python scripts/validate_card_resolution_contract.py` — pass
- `python scripts/validate_agent_context.py` — pass
- `python -m pytest tests -q` in `services/api` — 34 passed (includes `test_logic.py` and `test_notifications.py`)
- `npx tsc --noEmit` — pass

No production migration, real VAPID keys, commit, push, deploy, or `card-resolution-core-v1` work.

## Corrections applied (plan order)

1. **Auth and actor / endpoints / upserts**  
   Notification routes require an authenticated user. When Clerk JWT issuer is configured, a Bearer token is required. Settings UI sends Clerk tokens. Push endpoints must be HTTPS, non-private, and a recognized or configured provider host. Same-shop endpoint takeover returns 409 unless the prior owner disabled it.

2. **Delivery state machine**  
   Failed non-410/404 attempts retry with backoff. 410/404 disable the subscription. Events are marked delivered only when eligible targets are sent or expired. Pending batch is newest-first. Attempt rows are committed before the provider call. Delivery lookups include `shop_id`.

3. **Dedupe lifecycle**  
   Same `(shop_id, dedupe_key)` row is reused. Active pending/delivered updates increment without a new push. Acknowledge/resolve/cancel/failed reopen to pending and reset deliveries. Resolve endpoint added. In-process lock plus unique-constraint handling for concurrent creates.

4. **Worker isolation**  
   Notification drain runs even when Shopify auto-sync is off, on a separate session.

5. **Lock-screen and deep links**  
   Stored and pushed title/body are generic templates. `action_url` must be a relative `/admin/...` path. Service worker ignores off-origin and non-admin URLs.

6. **Session ownership**  
   `create_notification` flushes only; it does not commit the caller session.

7. **Secrets and enablement**  
   Root `.env.example` no longer names the VAPID private key. Default/placeholder subject does not enable push.

8. **Tests and CI**  
   Amendment acceptance cases are covered with a mocked provider. Gate path filters include `scripts/**` and env examples. Validator rejects a private key in the Next.js env example.

9. **Preferences**  
   Daily digest and quiet hours are hidden in the UI until implemented.

## Remaining risks for reviewers

- SQLite timezone-naive datetimes; production Postgres is timezone-aware. Retry comparison normalizes to UTC.
- In-process dedupe lock does not span multiple API processes; the unique constraint still applies.
- `create_all` will not alter already-created notification tables in an existing local DB.
- GitHub cross-platform review still has not run (no PR/commit).
