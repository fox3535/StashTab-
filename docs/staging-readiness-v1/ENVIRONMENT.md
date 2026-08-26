# Staging environment contract

## Isolation (approved)

| Resource | Rule |
| --- | --- |
| Database | New Neon project. Empty. No production clone. |
| API | New Railway **project**, API service only in slice 0. |
| Worker | Later, same staging Railway project, separate unlock. |
| Clerk | Dedicated staging application. Production tokens must fail. |
| Vercel | Deferred until frontend testing. |
| Convex | Deferred until UI/billing testing. |
| Shopify | None in slice 0. Later: disposable development store only. |
| Customer/vendor/card data | Forbidden. Synthetic only. |
| Secrets | No shared production database, credentials, Clerk tenant, or secret set. |

## Required process environment (slice 0)

| Variable | Staging value |
| --- | --- |
| `APP_ENV` | `staging` (exact) |
| `STASHTAB_ALLOW_DEV_IDENTITY` | Unset / false |
| `DEV_SHOP_ID` / `NEXT_PUBLIC_DEV_SHOP_ID` | Empty |
| Debug | Off (`DEBUG=false` or equivalent) |
| `CLERK_JWT_ISSUER` | Staging Clerk issuer |
| `CLERK_AUTHORIZED_PARTIES` | Staging Clerk / test origin (no production UI origin) |
| `CORS_ORIGINS` | Empty or staging-only; no production origin |
| `DATABASE_URL` | Staging Neon **runtime** user |
| `NOTIFICATIONS_BACKEND_ENABLED` | Unset / false |
| `VAPID_*` | Empty |
| `WEB_PUSH_ALLOWED_HOST_SUFFIXES` | Empty |
| `STASHTAB_TRUTH_MIGRATOR_ROLE` | **Not** on API or worker |
| Shopify tokens | Absent |

## Identity

- User = verified Clerk Bearer `sub`.
- Shop = membership for that user; shop header is an untrusted hint.
- Header-only user/shop is 401/403.
- Bypass cannot be enabled on staging.

Synthetic users: staging Clerk app only. Onboard via real API. Do not run `services/api/scripts/seed_dev.py` (or any local seed) against staging. Fixtures must check they target staging (env + host allowlist) and clean up idempotently.

## Shopify

Missing settings or tokens = sync **off**. Never on.
