# Checkpoint — F2 API deployment to Railway staging (executed and verified)

**Status:** `EXECUTED — VERIFIED — FAIL-CLOSED — CUTOVER STILL LOCKED`
**Deployed source:** protected `main` at `ec9f72c` (PR #33 merge commit); full
SHA `ec9f72c42c4f5ad0c0adf217c05c5f766033739c`
**Railway deployment:** `44317623` — `SUCCESS`, created 2026-09-04T23:19:51Z
**Prepared on:** `main` at `c9dcb19`; executed under a named owner unlock
**Verified:** 2026-09-04, read-only (D-043)
**Bound by:** DIRECTIVE-F2 / AMENDMENT-1.3.0; separate from the provisioning and
cutover unlocks
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

This checkpoint recorded the exact Railway staging **API-only** redeploy that
carries the merged F2 code; it now also records that deploy's execution and
read-only verification. The receive endpoint is **deployed but fail-closed**.
Cutover and receive-endpoint use stay separately locked, and no successful
receive has occurred.

## Scope (API service only)

| Item | Value |
| --- | --- |
| Service | Railway **API service only** — one service instance observed; no worker service; `cronSchedule` null |
| Source | protected `main` at `ec9f72c` — deployment `meta.commitHash` matched the pinned SHA |
| Autodeploy | **OFF** — `watchPatterns: []`; one manual deploy of the pinned SHA only |
| Environment | existing Railway **staging** environment (no new environment) |
| Database role | existing **pooled** `stashtab_api` runtime role (pgbouncer). The `stashtab_migrator` role never runs at deploy |
| Health | `GET /api/v1/health` |
| Readiness | `GET /api/v1/ready` |

## Verified OFF after this deploy

- Inventory-truth **cutover** stays OFF: `GET /api/v1/ready` reports
  `features.inventory_cutover: false`, and the Neon cutover rowcount is `0`. No
  `inventory_truth_cutover` row was created.
- **No feature flags** enabled: `notifications_backend`, `web_push`,
  `inventory_cutover`, `shopify_sync`, and `worker` all report `false`, with
  `reasons: []`.
- **Shopify, notifications, Web Push, worker jobs:** no worker service and no
  cron schedule; bounded runtime logs show zero worker, Shopify, Web Push,
  schema, migration, and seed activity. Two unrelated
  `GET /api/v1/sync/notifications` 503s are the pre-existing
  notifications-off path, not F2 activity.
- Deploying the merged code did **not** enable writes: the receive path stayed
  fail-closed and no receive row exists.

## Post-deploy verification — results (read-only; no seeded writes)

| # | Expected | Observed 2026-09-04 |
| --- | --- | --- |
| 1 | `GET /api/v1/health` → **200** | **200** `{"status":"ok","service":"mimir-api"}` (re-confirmed while writing this record) |
| 2 | `GET /api/v1/ready` → **200** | **200** `status: ready`, `app_env: staging`, `database.connected: true`, `identity.dev_bypass_allowed: false`, `schema.legacy/inventory_truth: true`, `schema.notifications: false`, all five `features` `false`, `reasons: []` |
| 3 | `POST …/receive` **unauthenticated** → **401** | **401** — exactly one such line in bounded runtime logs |
| 4 | `POST …/receive` **authenticated** → controlled **503** before any write | **503** `{"error":"FEATURE_NOT_READY","feature":"inventory_truth","message":"This operation is not enabled in this environment."}` — **exactly one** authenticated probe; owner-run, once |
| 5 | Neon staging row counts unchanged | Unchanged — see the snapshot table below |

### Probe ordering (step 4 proof)

The 503 occurred **after** authentication and membership resolution and
**before** any receive transaction or write:

- `GET /api/v1/shops/me/memberships` → **200** in the same window, so identity
  and shop membership resolved successfully; the probe was not rejected as 401
  or 403.
- `GET /api/v1/inventory/search?q=&limit=50` → **200**, so the pooled runtime
  role reads normally.
- The write path returned `FEATURE_NOT_READY` (503), not an authorization
  error, which is the cutover gate raising before the single-transaction
  receive write.
- Corroborated by Neon: every business/truth table still holds `0` rows, and
  neither probe marker exists.
- The single `OPTIONS …/receive` **200** line is CORS preflight, not a probe.

### Neon re-snapshot (pooled `stashtab_api` only)

Read-only session (`readonly=True`) over the **pooled** `stashtab_api` role
against `stashtab_staging`. No migrator credential, no privileged role, no
write, no seed.

| Item | Observed |
| --- | --- |
| Accessible tables | 13 |
| Business/truth tables | all `0` rows (11 tables), including `purchase_record`, `inventory_item`, `acquisition_lot`, `inventory_event` |
| Row-count digest (SHA-256 over sorted counts) | `7f92454515ec31678e05a1da695f1bb02ddba0b7f67a648db008566b22d066c9` — identical to the pre-probe baseline and stable across both post-probe runs |
| Identity | `shops = 2`, `shop_members = 2` |
| Cutover | `inventory_truth_cutover` rowcount `0` — OFF |
| `F2-PROBE-DO-NOT-USE` | **absent** |
| `F2-TEST-0001` | **absent** |
| Column | `purchase_record.client_idempotency_key` — `character varying(36)`, nullable |
| Index | `CREATE UNIQUE INDEX uq_purchase_record_shop_client_key ON public.purchase_record USING btree (shop_id, client_idempotency_key) WHERE (client_idempotency_key IS NOT NULL)` |
| Envelope grants | SELECT + INSERT on `inventory_item`, `purchase_record`, `acquisition_lot`, `inventory_event`; no table-wide UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER |
| Column-scoped UPDATE | `inventory_item.stock` and `.cost` true; `sku`, `name`, `id` false |
| Sequences with USAGE | 11, including the four F2 envelope sequences |
| Credential hygiene | Connection URL injected into the process environment only, never printed; cleared after use |

Verification used existing empty-state reads and the single owner-run
denied-write probe only. No data was seeded to probe. The 503 on the
authenticated receive call is the expected fail-closed result, not a defect.

### Process stability

Bounded runtime logs show one `Started server process`, one `Uvicorn running`,
and one `Application startup complete`, with no shutdown, crash, or restart
lines — one stable API process on the deployed SHA.

## Explicitly not this checkpoint

- Cutover unlock (gen-1 synthetic shop) — a separate named owner unlock. See
  `CHECKPOINT-F2-CUTOVER-PLANNING.md` (planning only).
- Any successful receive or other inventory write.
- Worker deploy, Shopify, notifications, Web Push, payments, Watch.
- Production deploy, production schema, privileges, or credentials.
- Any further deploy or redeploy, autodeploy enablement, flag change, grant
  change, seeding, or repeat receive call.

## Relationship to provisioning

Staging provisioning (column, index, and grants) is already applied and
verified — see `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md` and D-042. This
deployment carried the merged F2 **code** to the staging API. It changed no
schema and no privileges, and it did not unlock cutover: the post-deploy
re-snapshot above found the provisioned column, index, and grant envelope
byte-for-byte as recorded at provisioning, with all business tables still
empty. Provisioning is therefore **complete**; cutover and a successful receive
remain **separately locked**.
