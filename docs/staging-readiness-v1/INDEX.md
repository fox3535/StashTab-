# Staging readiness v1 — planning packet

**Slice:** `backend-foundation / staging-readiness-v1`  
**Baseline:** `main` merge `c3647a4eda37d355ed47f9e77ad667e4fda7930c` (not deployed)  
**Owner decisions:** APPROVED 2026-08-25 (`OWNER-DECISIONS.md`)  
**Freeze:** hashes in `freezes/FREEZE-v1.json` (manifest is not hashed)

Backend foundation is on `main`. It is **not deployed**. Staging is isolated rehearsal, not production.

## Packet files

| File | Contents |
| --- | --- |
| `TOPOLOGY.md` | Current backend shape and existing deploy files |
| `ENVIRONMENT.md` | Isolated staging env contract |
| `ROLES.md` | Database roles, grants, proof runtime cannot become migrator |
| `SCHEMA.md` | Migration order, unique membership index, `create_all` containment |
| `SAFEGUARDS.md` | 503 FEATURE_NOT_READY, readiness vs liveness, fail-closed sync |
| `REHEARSAL.md` | Empty DB, synthetic legacy, failure, rollback, backup |
| `CUTOVER.md` | Freeze, dual-write checks, recon = 0, abort |
| `FLAGS.md` | Feature flags and who may turn them on |
| `SMOKE.md` | Staging smoke list |
| `OPERATIONS.md` | Logs, health, break-glass |
| `RUNBOOK.md` | Operator runbook (replaces `DEPLOY.md` for this architecture) |
| `GATES.md` | Open gates classified by when they must close |
| `REVIEWS.md` | Independent planning reviews and bounded verification |
| `OWNER-DECISIONS.md` | Approved owner answers |
| `sql/provision-staging-roles.sql` | Reviewed one-time role script (not executed in this freeze) |
| `freezes/MANIFEST-SPEC.md` | How hashes are computed |

A slice-0 implementation directive is issued **after** freeze and is **not** a frozen file.

## Approved topology

New Railway staging project (API only) + new Neon staging database + dedicated Clerk staging app. Worker later in the same staging Railway project under a separate unlock. Vercel and Convex deferred. No shared production database, credentials, Clerk tenant, or secrets.

## Closed P0/P1 planning defects (specified here; implemented in slice 0)

1. Inventory-truth-dependent routes return `503 FEATURE_NOT_READY` when schema/cutover is unavailable — no raw missing-table 500.
2. Separate `/ready` from `/health`.
3. Staging/production startup does not `create_all` or leftover ALTER.
4. Missing settings/tokens mean Shopify sync is off.
5. `DEPLOY.md` is outdated; use `RUNBOOK.md`.
6. Mutable context/gate docs record merge `c3647a4` and not deployed.

## Smallest first implementation slice

`staging-readiness-v1 / slice-00-isolated-api` — configuration/readiness safeguards, controlled feature-unavailable responses, contain startup schema mutation, identity/shop isolation smoke, synthetic users/shops. No worker, Shopify, truth/notification migrators, VAPID, frontend, or production data.

## Freeze

This packet is frozen after bounded verification. Implementation of slice 0 still requires a named provisioning unlock. Do not create cloud resources from this freeze.
