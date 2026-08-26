# Slice-00 PR #2 review

**PR:** https://github.com/fox3535/StashTab-/pull/2  
**Head:** `360df00c9a5e7b14e33c65b0be7083d7e70de4ba`  
**Base:** `main` / `c3647a4eda37d355ed47f9e77ad667e4fda7930c`  
**Planning checkpoint:** `131bc1eed01f3e9b732e41cde039de6c15cea707`  
**Mode:** review only. No code change, merge, deploy, or cloud provision.  
**This file is uncommitted.**

## frontend-build skip (confirmed)

| Claim | Evidence |
| --- | --- |
| Job exists on PR #2 | Check run `frontend-build` on workflow `Card resolution contract gates`, run `32915325310`, job `98017773687` |
| Conclusion | `SKIPPED` (not success) |
| Why skipped | Workflow `on.pull_request` has **no** `paths:` filter. The `paths` job ran `python scripts/ci_pr_gate.py contract-and-backend frontend-build`. That internal detector set output `frontend-build` false because the PR diff has no `app/**`, `components/**`, `lib/**`, `public/**`, or package/tsconfig/next config files. The `frontend-build` job then used `if: needs.paths.outputs.frontend-build == 'true'` and was skipped. |
| Not a workflow-level path filter | `card-resolution-gates.yml` triggers on every pull request. The Card resolution workflow **did run** (`paths` success, `contract-and-backend` success). |
| Ruleset `21480534` | Protect main requires `sqlite`, `postgres`, `contract`, `contract-and-backend`, `frontend-build`, `pg-acceptance`. PR #2 `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`. GitHub is not treating the skipped `frontend-build` check as a missing required check. |
| Record | `SKIPPED — NOT APPLICABLE — TERMINAL` — **do not call this a pass** |

Required checks that **passed**: sqlite, postgres, contract, contract-and-backend, pg-acceptance.

## Criterion results

1. **`/health` is process liveness, no database** — Met. `health()` returns a static payload and does not open a session. Railway `healthcheckPath` remains `/api/v1/health`.
2. **`/ready` checks staging prerequisites without secrets** — Met for `/api/v1/ready`. It pings the database, reports identity/schema/feature flags, and 503s on missing DB, invalid `APP_ENV`, missing Clerk issuer/parties in staging/production, debug, notifications, Web Push, worker jobs, migrator role, or identity bypass. Payload is scanned so configured secret values cannot appear.
3. **Staging/production cannot run startup `create_all` or ad-hoc ALTER** — Met when `APP_ENV` is `staging` or `production`. Lifespan skips `init_db()`. `init_db()` and leftover ALTER raise if invoked.
4. **Local/test bootstrap cannot arm under staging/production** — Met. `bootstrap_legacy_schema()` requires `local` or `test`.
5. **Missing/invalid environment fails closed** — Met for identity bypass and readiness (`app_env_invalid`). Partial gap: empty `APP_ENV` still allows startup `init_db()` (existing local default). Not a merge blocker; must be set to `staging` before provision.
6. **Risky features default off** — Met. Notifications, Web Push, worker jobs, inventory cutover flag, and Shopify sync report off. Notification router is not mounted unless the backend flag is on.
7. **Missing Shopify settings/tokens cannot enable sync** — Met. Missing `system_settings` means auto-sync off. Empty store URL or token means no Admin API client.
8. **Inventory-dependent routes return controlled `503 FEATURE_NOT_READY`** — **Partial. P1.** Receive, trade receive, and POS finalize call `ensure_inventory_mutations_ready` and the app handler returns `{error: FEATURE_NOT_READY, feature: inventory_truth}`. Admin quantity PATCH and CSV quantity import **do not** call that gate. `_reject_if_truth_frozen` exists but is unused by those handlers. Missing truth tables can still 500 on PATCH/CSV. Incomplete cutover on PATCH/CSV is a string 503 `detail`, not the controlled body.
9. **Development seed refuses staging/production** — Met.
10. **No cloud resources, credentials, deploy config, or production migrations added** — Met. Role SQL is documentation only. No Railway/Neon/Clerk/Vercel/Convex/Shopify resources. `railway.toml` still probes `/api/v1/health`.
11. **Tests cover negative and cross-environment cases** — Mostly met for health/ready/DDL/seed/Shopify/worker defaults and identity isolation (existing suite). Gap: no HTTP test of admin PATCH/CSV missing-schema `FEATURE_NOT_READY`.
12. **Frozen staging specs and manifests remain valid** — Met. `python scripts/validate_staging_readiness_freeze.py` OK. Hashed packet files are unchanged since `131bc1e`.

## Focused reviews

### Architecture
Receive/POS/trade correctly share one fail-closed gate. Admin quantity PATCH/CSV are a second path that still talks to truth via `cutover_status` / `apply_adjustment` without the slice-00 error type. Liveness vs readiness split is correct. Railway must keep probing `/health`.

### Application-security
Identity bypass cannot arm on staging/production. Readiness does not echo secrets. Clerk issuer/parties are required for staging ready=200. Debug on in staging fails ready. No credentials added to git.

### Database-security
Staging/production startup cannot `create_all` or leftover ALTER. Empty `APP_ENV` still allows DDL — set `APP_ENV=staging` before any hosted process. Role SQL is not executed by this PR.

### Operations
Ready 503 vs health 200 is the correct Railway split. Worker `main()` exits when jobs are disabled, so a mistaken worker service would not tick. Hosted staging still needs `APP_ENV=staging`, `debug` off, Clerk issuer/parties, and no VAPID/notification/worker flags.

### Adversarial
Missing Shopify row/token cannot turn sync on. Cross-shop identity tests remain in the suite. The remaining attack is unauthenticated or authenticated PATCH/CSV against a DB without truth tables: likely 500 instead of a controlled 503 (information leak of schema absence, not a write).

## Findings

### P0/P1 blocking ready
- **P1.** Admin quantity PATCH and CSV quantity import are not wired to `ensure_inventory_mutations_ready` / `FEATURE_NOT_READY`. Missing inventory-truth tables can 500. Incomplete cutover returns a string 503, not the frozen JSON body. Helper `_reject_if_truth_frozen` is unused by those routes.

### Required before merge
- Wire PATCH and CSV quantity writes through the same `FEATURE_NOT_READY` gate used by receive/POS/trade, including missing-table and incomplete-cutover cases.
- Add HTTP tests for those two routes under missing truth schema.

### Required before provisioning
- Set `APP_ENV=staging`, debug off, Clerk issuer and authorized parties, empty VAPID, notifications off, worker jobs off, no Shopify tokens.
- Neon roles from `sql/provision-staging-roles.sql` run by the Neon owner, not this PR.
- Confirm Railway healthcheck stays `/api/v1/health`.

### Required before staging activation
- Operator bootstrap of **legacy** live tables only (not truth/notification).
- Identity and shop-isolation smoke on the hosted API.
- Worker service must not be started.

### Non-blocking follow-up
- Treat empty/invalid `APP_ENV` as forbidding startup DDL, not only `staging`/`production`.
- Readiness reports process-level Shopify/cutover flags, not per-shop credential presence.

## Verdict (initial review)

PR #2 stayed **draft**. The P1 PATCH/CSV `FEATURE_NOT_READY` gap was a merge blocker.

`frontend-build`: `SKIPPED — NOT APPLICABLE — TERMINAL`

## Bounded correction (authorized)

Wired admin quantity PATCH and quantity CSV through `ensure_inventory_mutations_ready` via `_reject_if_truth_frozen` (PATCH) and a pre-apply CSV check. Missing schema is detected with inspect, not a failing truth-table query. Mixed price-plus-quantity PATCH calls the guard before any field write. Price-only PATCH does not call the guard. CSV detects quantity-changing intent and rejects the whole file with `503 FEATURE_NOT_READY`; no rows apply. `CSV-COST-FEEDBACK-GATE` remains open.

### Focused verification

- Application-security: quantity writes fail closed with the controlled body; cross-shop PATCH is 403/404 before mutation.
- Data-integrity: mixed PATCH changes neither field; multi-row quantity CSV applies nothing on 503.
- Adversarial: missing truth tables no longer 500 on these routes; no silent skip of quantity rows.

### Local evidence

- Focused PATCH/CSV/identity tests passed.
- SQLite: 197 passed, 46 skipped.
- PostgreSQL harness: 46 passed.
- Frozen validators, agent context, card-resolution contract, and `tsc --noEmit` passed.
- Secret scan and trailing-whitespace check on correction files: clean.

P1 is closed for these paths. Remaining items are still pre-provisioning / activation, not merge code defects. PR #2 should stay draft until the owner marks it ready.
