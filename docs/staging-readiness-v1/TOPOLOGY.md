# Current backend topology

**Baseline:** `c3647a4eda37d355ed47f9e77ad667e4fda7930c` on `main`, not deployed.

## Processes

| Piece | Code | Role today |
| --- | --- | --- |
| FastAPI API | `services/api/app/main.py` | HTTP. Calls `init_db()` on startup (must be contained in staging). Mounts inventory, sales, admin, sync, reports, shows. Notification router only if notifications backend enabled. |
| Worker | `services/api/worker.py` | Loop: every shop, optional Shopify full sync, then notification recover/process if the flag is on. **Not provisioned in slice 0.** Today missing settings means auto-sync on — slice 0 must invert that in code. |
| PostgreSQL | `docker-compose.yml` local; Neon in outdated `DEPLOY.md` | System of record. Multi-tenant via `shop_id`. |
| Redis | compose + redis URL in config | Unused by this merge. Do not add Redis to staging. |
| Clerk | `app/auth/clerk.py`, `app/auth/identity.py` | JWT `sub` + `ShopMember`. Staging/production refuse header bypass. |
| Shopify | Shopify client, sync worker, admin credential routes | Live Admin API if credentials are stored. Slice 0 stores none. |
| Notification backend | notification logic + `notifications_truth/` | Durable intent + optional Web Push. Default off. |
| Convex / Next.js | repo root | UI and billing shell. Deferred for staging. |
| Health | `GET {api_prefix}/health` | Liveness only. Readiness is specified in `SAFEGUARDS.md`. |

## Existing deploy files (assumptions, not permission)

| File | What it assumes |
| --- | --- |
| `DEPLOY.md` | **Outdated** for this architecture. Production-shaped checklist: seed from local, live Clerk, Shopify connect. Do not execute it. Use `docs/staging-readiness-v1/RUNBOOK.md`. |
| `services/api/railway.toml` | Docker build, uvicorn `$PORT`, health `/api/v1/health`. API only. |
| `services/api/Dockerfile` | Copies `app/` and `worker.py`. Default CMD uvicorn 8000. |
| `docker-compose.yml` | Local Postgres 16 + Redis. Single user. Not staging. |

No GitHub workflow deploys on merge to `main`. Staging must be **new** projects.

## Approved staging topology

Separate Railway project (API only) + separate Neon + dedicated Clerk. Worker later in the staging Railway project. No Vercel/Convex in slice 0.

## Data planes

- Live snapshot: `inventory_item.stock` remains operational quantity.
- Inventory-truth: eight tables, migrator only, not slice 0. Dual-write is in code; without schema/cutover, routes must return `503 FEATURE_NOT_READY`.
- Notifications: twelve tables, migrator only, flag off.

## Convex

Deferred. A later Convex staging deployment must be dedicated; shared Convex mixes signups into production billing.
