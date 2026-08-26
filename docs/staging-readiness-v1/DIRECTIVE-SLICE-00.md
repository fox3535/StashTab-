# Implementation / provisioning directive

**Slice:** `staging-readiness-v1 / slice-00-isolated-api`
**Frozen packet:** `docs/staging-readiness-v1/freezes/FREEZE-v1.json`
**Baseline:** `c3647a4eda37d355ed47f9e77ad667e4fda7930c` (not deployed)
**Status:** `COMPLETED, NOT MERGED, NOT DEPLOYED` — code accepted 2026-08-25; no cloud provision

This file is **not** part of the freeze hashes. It does nothing until a named human unlock.

## In scope

1. Staging configuration and readiness safeguards (`SAFEGUARDS.md`).
2. Controlled `503 FEATURE_NOT_READY` on inventory-truth-dependent routes.
3. Disable leftover startup `create_all` and ALTER when `APP_ENV` is `staging` or `production`.
4. Fail-closed worker/Shopify defaults in **code** (missing settings/tokens = off). Do not provision a worker.
5. Written setup plan for a separate Railway API project, separate Neon, dedicated Clerk.
6. Identity and shop-isolation smoke tests.
7. Staging-only synthetic fixture helper with target checks (not the local seed script).

## Out of scope

Worker service; Shopify; inventory-truth migrator apply; notification migrator; VAPID/Web Push; Vercel/Convex; production data or credentials; executing role SQL against a live Neon; creating cloud accounts.

## Code to implement (after unlock, still no cloud create unless separately approved)

- `GET /api/v1/ready` as specified in `SAFEGUARDS.md`. Keep `GET /api/v1/health` liveness-only. Railway continues to probe health, not ready.
- Map missing truth schema / incomplete cutover to `503` `{ "error": "FEATURE_NOT_READY", "feature": "inventory_truth" }` on receive, trade-receive, POS finalize, quantity adjust, quantity PATCH, CSV stock overwrite. No raw missing-table 500.
- If `APP_ENV` is `staging` or `production`, skip `create_all` and leftover column ALTER on API (and worker module) startup. Fail boot if those paths run.
- Worker helper: missing `system_settings` → auto-sync off; missing Shopify tokens → no Admin API. Worker process is still not started.
- Staging synthetic fixture script: require `APP_ENV=staging`, refuse local seed, allowlist staging DB host, idempotent cleanup.

Tests (local/CI only): ready payload has no secrets; health does not need DB; FEATURE_NOT_READY when truth tables absent; staging startup does not ALTER; missing settings ⇒ sync off; identity 401/403 cross-shop.

## Provisioning plan (human, after unlock — not this file)

1. New Neon project, empty, no clone.
2. Owner runs `sql/provision-staging-roles.sql` (or explicitly authorizes it). Set passwords out of git.
3. Migrator identity bootstraps **legacy** live schema only. API uses `stashtab_api`.
4. New Railway project, API only, root `services/api`, health `/api/v1/health`.
5. New Clerk staging app. Bind issuer and authorized parties to staging only.
6. Env: `APP_ENV=staging`, debug off, bypass off, notifications off, VAPID empty, no Shopify, no migrator role-create var, runtime DB URL only.
7. Smoke: `SMOKE.md` slice 0.
8. Stop. No worker. No truth/notification apply.

Incident owner: Chris. Break-glass: manual, time-bounded, logged, then rotate.

## Unlock required

A named human message authorizing this slice. Until then: no accounts, no secrets, no migrate, no deploy, no commit from this directive.
