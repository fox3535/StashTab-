# Slice-00 isolated API code — acceptance

**Slice:** `staging-readiness-v1 / slice-00-isolated-api-code`
**Status:** `COMPLETED, NOT MERGED, NOT DEPLOYED`
**Decision:** APPROVED by named human owner 2026-08-25
**Planning checkpoint:** `131bc1eed01f3e9b732e41cde039de6c15cea707`
**Baseline:** `c3647a4eda37d355ed47f9e77ad667e4fda7930c` (not deployed)

This record is not part of the freeze hashes.

## Evidence accepted

- Separate liveness (`/api/v1/health`) and readiness (`/api/v1/ready`)
- Staging/production startup DDL disabled
- Named legacy bootstrap is local/test only
- Notifications, Web Push, cutover, worker, and Shopify default off
- Missing Shopify configuration means skip, never auto-enable
- Development seed rejects staging/production
- Controlled `503 FEATURE_NOT_READY` for unavailable inventory-truth paths, including stock/CSV freeze
- SQLite: 192 passed, 46 PostgreSQL-only skipped
- Disposable PostgreSQL: 46 passed
- Frontend typecheck and frozen validators passed
- Review correction for controlled stock/CSV freeze response passed

## Explicitly not authorized by this acceptance

Railway, Neon, Clerk, Vercel, Convex, or Shopify resources; deployment; schema apply; merge to `main`; ready-for-review beyond a draft PR.
