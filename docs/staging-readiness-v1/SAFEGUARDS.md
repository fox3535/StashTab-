# Staging safeguards (planning defects closed)

These rules are part of the frozen packet. Slice 0 implements them in code. They are not yet running in any hosted environment.

## 1. Controlled `503 FEATURE_NOT_READY`

Inventory-truth-dependent writes must never return a raw missing-table `500`.

**When:** `APP_ENV` is `staging` or `production`, and either (a) inventory-truth tables are absent, or (b) the shop has no completed gen-1 cutover.

**HTTP:** `503`  
**JSON (no table names, no connection strings, no stack traces):**

- `error`: `FEATURE_NOT_READY`
- `feature`: `inventory_truth`
- `message`: a short operator-safe sentence that the operation is not enabled yet

**Covered operations (slice 0: all of these stay unavailable):**

- Receive / intake commit
- Trade receive that dual-writes truth
- POS / sale finalize (outbound)
- Inventory adjustment / reversal
- Admin stock PATCH that mutates quantity
- CSV stock overwrite

**Mapping:**

- Missing truth table or failed cutover lookup because the table does not exist → `503 FEATURE_NOT_READY` (not `500`)
- Cutover row missing or status not `complete` → `503 FEATURE_NOT_READY` (not an unhandled freeze exception)
- After a later approved cutover, an explicit operational freeze may keep the same `503` with `feature` still `inventory_truth`

Notification HTTP stays absent while the backend flag is off (`404` is acceptable). Do not create notification tables in slice 0.

## 2. Liveness vs readiness

| Endpoint | Purpose | Railway |
| --- | --- | --- |
| `GET /api/v1/health` | Process liveness only. No database. | Keep as `healthcheckPath`. |
| `GET /api/v1/ready` | Readiness. Proves database connectivity, required identity configuration, schema presence flags, and feature-gate state. | **Not** the Railway restart probe in slice 0. |

Readiness **200** for slice 0 means: process can talk to staging Postgres, Clerk issuer and authorized parties are configured, identity bypass is off, notification/Web Push/Shopify/worker/cutover flags are off. Truth and notification schemas **may be absent**; report them as booleans, do not fail slice-0 readiness solely because they are absent.

Readiness **503** when: database ping fails, or `APP_ENV=staging` with missing Clerk issuer/authorized parties, or identity bypass would be allowed, or debug is on, or notification/Web Push would be on, or migrator role-creation env is set on the runtime process.

Readiness body may include booleans and enum-like schema flags only. Never secrets, VAPID material, database URLs, role passwords, or Clerk secret keys.

## 3. Startup schema mutation contained

When `APP_ENV` is `staging` or `production`:

- Do **not** call `Base.metadata.create_all`
- Do **not** run leftover `_ensure_columns` / `ALTER TABLE … IF NOT EXISTS` on API or worker startup
- If those paths are invoked, fail closed at boot (do not silently ALTER)

Legacy live tables for slice 0 (shops, members, settings, and other existing `Base` models needed for onboard/identity) are created **once** by an operator using the migrator identity, never by the Railway API runtime role.

Truth and notification tables remain migrator-only in later slices.

Runtime roles have no `CREATE` on `public`.

## 4. Worker / Shopify fail-closed

Missing `system_settings` row **means auto-sync is off**. Missing or empty Shopify tokens **means no Admin API calls**. Never treat absence as “sync on.”

Slice 0 does not provision a worker. The fail-closed default must still be implemented in shared worker/settings code in slice 0 so a later worker unlock cannot inherit default-on behaviour.

`STASHTAB_TRUTH_MIGRATOR_ROLE` must be unset on API and worker. Runtime must not `CREATE ROLE`.

## 5. Deploy docs

`DEPLOY.md` is **not** an executable staging (or current-architecture production) guide. Staging operators use `RUNBOOK.md` in this packet.
