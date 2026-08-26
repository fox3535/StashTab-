# Staging runbook (slice 0 and later rehearsal)

**Do not follow `DEPLOY.md`.** That file is outdated for this architecture.

Incident owner and break-glass approver: **Chris**. A second qualified human is required before production readiness.

## Slice 0 — create isolation (human, after named unlock)

1. Create a **new** Neon project. Empty database. No clone.
2. Create a **new** Railway project. One API service from `services/api`. No worker.
3. Create a **new** Clerk application. Issuer and authorized parties bound to this staging API/testing origin only. Slice 0 has no Vercel UI; do not point authorized parties at production.
4. Put **runtime** Neon credentials on Railway API only (not migrator, not owner).
5. Set first-boot env from `ENVIRONMENT.md` / owner decision 6.
6. Do not attach production Clerk, Neon, Shopify, VAPID, or Convex secrets.

No accounts are created by this planning freeze.

## After API code for slice 0 exists (still not this freeze)

1. As Neon owner, run reviewed `sql/provision-staging-roles.sql` (or explicitly authorize it).
2. As migrator, bootstrap **legacy** live schema only. Switch API to `stashtab_api`.
3. Confirm `/health` 200 and `/ready` 200 with truth/notification schema flags false and features off.
4. Run identity/shop-isolation smoke in `SMOKE.md` slice 0.
5. Confirm receive/POS/adjust return `503 FEATURE_NOT_READY`.
6. Confirm `seed_dev` / local seed is not used. Synthetic fixtures only, with target checks.

## Break-glass

- Chris approves manually. Time-bound. Log who, why, start, end.
- After: rotate Neon passwords, Clerk secret if exposed, Railway env; restart; confirm old credentials fail.

## Abort

Stop if any production credential, production Shopify token, production data, identity bypass, notification/Web Push on, or runtime role-creation env appears.

## Later slices (not slice 0)

Worker, Shopify development store, inventory-truth migrator, notification schema, Vercel, Convex — each needs its own named unlock. See `GATES.md`.
