# Checkpoint — F2 API deployment to Railway staging (prepared, not executed)

**Status:** `PREPARED — NOT EXECUTED — AWAITING NAMED DEPLOYMENT UNLOCK`
**Deploys:** protected `main` at the eventual docs-merge SHA (this record's PR
merge commit; fill in after merge)
**Base for this record:** `main` at `c9dcb19`
**Bound by:** DIRECTIVE-F2 / AMENDMENT-1.3.0; separate from the provisioning and
cutover unlocks
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

This checkpoint describes the exact Railway staging **API-only** redeploy that
carries the merged F2 code. It does **not** authorize execution. Cutover and
receive-endpoint use stay separately locked. No Railway/Neon/Clerk contact
occurs until a named owner unlock.

## Scope (API service only)

| Item | Value |
| --- | --- |
| Service | Railway **API service only** — no worker service, no cron job |
| Source | protected `main` at the docs-merge SHA |
| Autodeploy | **OFF** — manual deploy of the pinned SHA only |
| Environment | existing Railway **staging** environment (no new environment) |
| Database role | existing **pooled** `stashtab_api` runtime role (pgbouncer). The `stashtab_migrator` role never runs at deploy |
| Health | `GET /api/v1/health` |
| Readiness | `GET /api/v1/ready` |

## Remains OFF at this deploy

- Inventory-truth **cutover** stays OFF; no `inventory_truth_cutover` row is
  created.
- **No feature flags** enabled.
- **Shopify, notifications, Web Push, worker jobs:** off / not scheduled.
- Deploying the merged code does **not** enable writes; the receive path stays
  privilege-locked until cutover is separately unlocked.

## Post-deploy verification (read-only; no seeded writes)

1. `GET /api/v1/health` → **200** `{"status":"ok"}`.
2. `GET /api/v1/ready` → **200** (database reachable via the pooled role).
3. `POST /api/v1/admin/inventory/receive` **unauthenticated** → **401**.
4. `POST /api/v1/admin/inventory/receive` **authenticated** → **controlled 503**
   `FEATURE_NOT_READY` (SQLSTATE `42501` fail-closed path) **before any write**;
   no row is created because cutover is OFF.
5. Neon staging **row counts unchanged**: all business/truth tables still `0`;
   identity still `2` shops / `2` owners. Compare against the provisioning
   reconciliation baseline in
   `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`.

Verification uses existing empty-state reads and denied-write probes only. Do
**not** seed data to probe. A 503 on the authenticated receive call is the
expected fail-closed result, not a defect.

## Explicitly not this checkpoint

- Cutover unlock (gen-1 synthetic shop) — a separate named owner unlock.
- Any successful receive or other inventory write.
- Worker deploy, Shopify, notifications, Web Push, payments, Watch.
- Production deploy, production schema, privileges, or credentials.
- Contacting Railway / Neon / Clerk before the named unlock.

## Relationship to provisioning

Staging provisioning (column, index, and grants) is already applied and
verified — see `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md` and D-042. This
deployment carries the merged F2 **code** to the staging API. It changes no
schema and no privileges, and it does not unlock cutover.
