# Owner decisions — approved 2026-08-25

**Status:** APPROVED by named human owner Chris.  
**Baseline:** `main` merge `c3647a4eda37d355ed47f9e77ad667e4fda7930c` (not deployed).  
These answers freeze the staging topology. They do not authorize provisioning until a named slice unlock.

## 1. Slice-0 resources — approved

- One completely separate Railway staging project with **API service only**.
- One completely separate Neon staging project/database.
- One dedicated Clerk staging application.
- Worker is added later **inside the staging Railway project** under a **separate unlock**.
- Vercel staging is deferred until frontend testing.
- Convex staging is deferred until UI/billing testing.
- No staging resource may share a database, credentials, Clerk tenant, or secret set with production.

## 2. Data — approved

- No production database clone.
- No production vendor, customer, or card data.
- Synthetic staging shops, users, cards, inventory, and transactions only.
- Any future sanitized production-derived dataset requires a separate privacy/security approval.

## 3. Shopify — approved

- No Shopify connection in slice 0.
- No Shopify tokens in the slice-0 environment.
- A later Shopify slice may use only a disposable development store.
- Missing settings or tokens **must mean sync is off, never on**.

## 4. Database-role ownership — approved

- Prepare a reviewed, idempotent one-time provisioning script (`sql/provision-staging-roles.sql`).
- The Neon project owner executes or explicitly authorizes execution of that script.
- API and worker runtime identities cannot create roles, own truth/notification tables, inherit migrator privileges, or assume the migrator role.
- `STASHTAB_TRUTH_MIGRATOR_ROLE` or equivalent role-creation behaviour stays disabled in API and worker environments.
- Migrator credentials are temporary, separate, audited, and absent from runtime services.

## 5. Incident and break-glass — approved

- Chris is the initial staging incident owner and break-glass approver.
- Break-glass use must be manual, time-bounded, logged, and followed by credential rotation/revocation.
- A second qualified human owner is required before production readiness.

## 6. First-boot settings — approved

- `APP_ENV=staging`
- Debug off
- Local/test identity bypass off
- Notification backend off
- No VAPID values
- Web Push off
- Worker not provisioned/running
- Shopify absent and sync off
- Inventory cutover off
- No receive, POS, adjustment, outbound, or notification feature activation
- No production credentials

## 7. Seed policy — approved

- Never run the local development seed script against staging.
- Use a separate, staging-only synthetic-fixture mechanism with explicit target checks and idempotent cleanup.

## Production-only (not authorized here)

Live VAPID / Web Push; production membership unique index on a production DB; `CSV-COST-FEEDBACK-GATE`; card-resolution core; security-assurance program; DNS pinning for future custom push hosts; a second production break-glass owner.
