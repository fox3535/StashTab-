# Staging smoke tests

Run in this order. Fail = stop.

## Slice 0 (API only, no truth schema, no worker)

1. `GET /api/v1/health` 200 (liveness; no DB required).
2. `GET /api/v1/ready` 200; body shows `app_env=staging`, database connected, identity configured, bypass false, debug false, notifications off, web push off, inventory cutover false, shopify sync off, worker not running; truth/notification schema flags false. No secrets in body.
3. `GET /api/v1/ready` with DB stopped (lab) → 503, still no secrets.
4. No Bearer → 401 on protected routes.
5. Valid **production** Clerk token → rejected (wrong issuer).
6. Valid **staging** Clerk token, no membership → 403.
7. Onboard shop; member can read shop-scoped data.
8. `X-Shop-Id` of another shop → 403.
9. Header-only user/shop → 401/403.
10. `STASHTAB_ALLOW_DEV_IDENTITY` even if set → ignored.
11. Inspect DB: no `inventory_event`, no `notification_event`.
12. Notification HTTP routes 404.
13. Receive, POS finalize, adjustment, outbound quantity write → `503` with `error=FEATURE_NOT_READY` (not 500).
14. Confirm local seed script was not used. Synthetic fixtures only.

## Slice 1 (after inventory migrator + gen-1 for shop A) — not slice 0

15. Receive on shop A succeeds; snapshot and events agree.
16. Sale (outbound) shop-scoped.
17. Adjustment + reversal only if that path is unlocked; else still FEATURE_NOT_READY.
18. Shop B cannot see shop A SKUs/events.
19. Recon = 0.
20. Restart API; still recon = 0.

## Slice 2 (worker, no live Shopify)

21. Worker up with empty Shopify credentials. Logs show no Admin API calls.
22. Missing settings row: auto-sync off (never on).
23. If a development store is later approved: still **no** production writes.

## Slice 3–4 and restore

24. Notification schema exists; HTTP still 404 while flag off.
25. Flag on, VAPID empty, mocked transport: durable intent, no browser push, cross-shop isolation.
26. Restore backup; identity still passes. Worker stopped; API still serves identity.
