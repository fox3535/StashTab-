# StashTab — Master Product and Build Plan

> **How to use this file:** Agents read this before work, then verify the exact
> current state in `docs/agent-context/CURRENT.md` and the relevant frozen
> contract. Chat is for decisions; it is not durable project memory.
>
> **Last reconciled:** 2026-08-27 — staging identity accepted, Convex removed,
> inventory schema applied (D-028), inventory read smoke accepted (D-029);
> card-resolution intake/abstention merged on `main` `6a266b1` (PR #13,
> D-034), feature off, not deployed; F0 exit passed for frontend recovery
> (D-035); F1 slice-01 (authenticated shell + read-only inventory) approved
> (D-036); my-shop memberships read completed locally (D-037), not merged,
> not deployed. Frontend implementation still awaits a named unlock.
> Writes, notifications, Shopify, payments, Watch, and Web Push remain
> off. This is not production approval.
>
> **Partner repo (reference only, do not push there):** `https://github.com/OdinFury-D/Mimir.git`  
> **Vendored brain in this repo:** `vendor/mimir-partner/` (Python reference snapshot)

---

## Architecture

```text
Phone / Browser
      ↓
Next.js (TypeScript)     ← UI: mobile POS + admin + landing
      ↓
FastAPI (Python)         ← Brain: port logic from the partner Python snapshot
      ↓
PostgreSQL               ← Inventory, sales, sync outbox (multi-tenant via shop_id)

Clerk = identity + billing shell
Convex is not part of the architecture. FastAPI + Neon own application data.
```

**Do NOT rewrite business logic in TypeScript.** Port Python from:
`vendor/mimir-partner/`

---

## Honest capability status

| Capability | Current status |
|---|---|
| Fail-closed Clerk/shop identity | Built; staging smoke accepted |
| Staging API and Neon roles | Running in isolated staging |
| Base identity schema | `shops` and `shop_members` on staging |
| Inventory live + truth schema | Applied to staging Neon only (D-028); tables empty |
| Inventory read-only search | Authenticated empty-table smoke accepted on staging (D-029); writes off |
| Mobile POS, admin, Shopify, reports, show/P&L | Existing foundations; preserve and optimize |
| Inventory truth receive/outbound/adjust slices | Accepted code on `main`; staging schema applied; cutover/routes incomplete |
| Notification backend 1.1.2 | Accepted code on `main`; staging schema, worker, and live push off |
| Card-resolution workflow | Merged on `main` `6a266b1` (PR #13); feature off; not deployed |
| Frontend | Substantial current and legacy work; cohesive recovery/redesign pending |
| Payments/accounting | Labels/foundations only; real capture and subledger not built |
| Portfolio/Market Watch | Product direction/contracts only; not built |
| Production launch | Not complete and not authorized |

`FEATURE_PARITY.md` records historical capability parity, not production
readiness. Existing code must still pass current identity, integrity, security,
staging, and UX gates.

## Current build sequence

### F0 — Backend foundation (exit passed for frontend recovery)

Goal: establish trustworthy identity, schema ownership, inventory evidence,
card resolution, notification mechanics, and staging operations before broad UI
redesign or production rollout.

1. **Identity and isolated staging** — completed and accepted on staging.
2. **Inventory schema rehearsal** — completed and applied to staging Neon only
   (D-028). Tables empty. Routes not enabled.
3. **Inventory read-only search** — completed and accepted on staging
   (D-029). Empty-table search only. Writes stay off.
4. **Card-resolution intake/abstention** — merged on `main` `6a266b1`
   via PR #13 (D-034). Feature off. Not deployed. Staging/production
   schema and flags remain off.
5. **Inventory truth write staging smoke** — later named write unlock.
   Not an F0 frontend-recovery blocker. Authenticated read contracts
   already exist. Do not seed merely to finish D-029 PATCH/checkout
   probes.
6. **Notification staging mechanics** — later hosted rehearsal with delivery
   disabled. Local/PostgreSQL isolation is accepted. Live Web Push remains
   a separate gate.
7. **Production security/operations** — restore drill and production
   break-glass remain production gates. Identity, roles, CI, readiness,
   and fail-closed flags already cover frontend recovery.

The full SOC 2 program, payments, Watch, production deployment, live Shopify,
and polished notification UI do not have to finish before frontend recovery.

### Backend-foundation exit gate

**Status:** `PASSED FOR FRONTEND RECOVERY` (D-035) on `main`
`6a266b10639df2931e1bd37d4040b49a0efd0bd2`.

Recorded:

- staging identity/shop isolation accepted (D-025);
- inventory schema applied and authenticated read smoke accepted (D-028,
  D-029); local/PostgreSQL truth paths accepted on `main`;
- card-resolution intake/abstention merged, feature off (D-034 / PR #13);
- notification isolation proven locally/PostgreSQL; live Web Push off;
- no open foundation P0/P1 blocks UI integration against disabled writes;
- Clerk + FastAPI header contracts exist for a local frontend test loop.

This is not production approval. Writes, notifications, Shopify, payments,
Watch, workers, and Web Push stay disabled. Frontend recovery may begin
against read-ready APIs and explicit not-ready write states.

### F1 — Frontend recovery and redesign (planning approved; code awaiting unlock)

F0 exit passed for frontend recovery (D-035). Slice-00 inventory is
recorded. First code slice is approved (D-036):
`frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`.
The shop-memberships list prerequisite is accepted locally (D-037) and
is not merged. Frontend implementation still requires a named unlock.
Do not start frontend code from this plan.

Owner rules for slice-01:

- FastAPI shop membership is shop-context authority.
- A stored/local shop ID is a selection preference only. It cannot grant
  access and must match current memberships.
- One membership auto-selects. Several memberships show an authorized
  shop selector. Stale or unauthorized preference is discarded.
- Never use caller-supplied user headers or a silent development shop
  fallback.
- Explicit sign-out in the authenticated desktop shell and mobile
  navigation. Landing and public marketing stay public.
- First live backend screen is read-only inventory search.
- Shopify connection/sync, POS checkout/selling, intake commit, resticker
  writes, CSV quantity writes, notification settings and service worker,
  payments, and Watch stay deferred and visibly not-ready. Disabled
  actions must explain that the feature is not ready; they must not look
  successful or silently do nothing.

Planning packet: `docs/frontend-recovery-v1/`.

1. Inventory every current page and preserved legacy UI change, including its
   purpose, screenshots, data dependencies, and merge status.
2. Recover valuable owner/partner work through focused branches. Never bulk-copy
   a dirty legacy tree over current `main`.
3. Define a cohesive vendor-first information architecture and design system
   for desktop admin and mobile/show POS.
4. Rework onboarding, dashboard, intake, inventory, POS, trades, shows,
   reconciliation, settings, and exception/review queues against accepted APIs.
5. Preserve barcode/label workflows, fast show-floor use, accessibility,
   responsive behavior, and explicit loading/offline/error states.
6. Use visual regression, browser smoke, API-contract tests, and direct owner
   review for each page slice.
7. Never move Python calculations into React or revive Convex/starter billing.

### F2 — Vendor financial operations

Extend existing `Sale`, `PendingTrade`, and `ShowSession` behavior with
receipt identity, cash sessions, exact-money migration, immutable operational
subledger, processor reconciliation, and accountant-reviewed exports. StashTab
does not hold funds or operate escrow.

### F3 — Market data and Watch

Use licensed point-in-time observations and deterministic metrics before agent
narratives. Portfolio/Market Watch remains advisory: no automatic buying,
selling, repricing, listing, or inventory mutation.

### F4 — Production readiness and launch

Production requires separate evidence and approval for migrations, roles,
reconciliation, backups/restores, monitoring, incident response,
privacy/vendor controls, payments, deployment, and rollback.

## Partner-brain integration method

`vendor/mimir-partner/` is read-only domain knowledge, not a runtime
dependency. For every feature derived from it, the slice plan must record:

1. partner source file, class/function, and observed behavior;
2. current StashTab implementation and tests;
3. behavior to preserve, optimize, defer, or retire—with reason;
4. target FastAPI module, database contract, and API boundary;
5. golden fixtures/parity tests using synthetic data;
6. tenant, idempotency, money, audit, and failure-mode requirements;
7. owner/partner review evidence before declaring parity.

Port business behavior, not obsolete desktop or single-shop assumptions.
Prefer incremental adapters over rewrites. If current StashTab logic is
stronger, keep it and document why.

---

## Existing Shopify sync foundation (preserve; disabled on staging)

- [x] Background worker (`worker.py`)
- [x] Full `_process_sync_outbox()` with product create/update
- [x] `_pull_shopify_orders()` — inbound orders
- [x] Per-shop Shopify credentials
- [x] Online sale toast (polling)
- [x] Admin: Connect Shopify settings page
- [x] Verify Shopify consistency

---

## Existing admin foundation (preserve; redesign after F0)

| Mimir screen | Admin route | Status |
|---|---|---|
| ManualIntakeFrame | `/admin/intake` | ✅ singles + sealed |
| StagingDockFrame | `/admin/staging` | ✅ + apply trade values |
| InventoryManagerFrame | `/admin/inventory` | ✅ inline edit |
| ReviewSyncFrame | `/admin/shopify/review` | ✅ |
| ShopifySyncFrame | `/admin/shopify/sync` | ✅ |
| SettingsFrame | `/admin/settings` | ✅ |
| import_engine | `/admin/import` | ✅ |
| Resticker queue | `/admin/resticker` | ✅ |

---

## Existing SaaS shell (not a production-launch claim)

- [x] Clerk Billing tiers (Free / Pro) — admin gated via `<Protect>`
- [x] Onboarding: sign up → create shop → connect Shopify
- [x] Team invites
- [x] Deploy docs: `DEPLOY.md`, `Dockerfile`, `railway.toml`
- [x] StashTab landing rebrand
- [x] PWA icons (192/512 PNG)
- [ ] Custom domain — ops step at deploy time

---

## Historical feature-parity checklist

These checks mean a foundation exists; they do not mean the capability is
currently staged, production-ready, or UX-complete.

- [x] Manual intake (single + sealed)
- [x] Staging dock + batch commit
- [x] Apply trade values to staging
- [x] Full inventory vault (filters, inline edit)
- [x] Live POS / mobile checkout
- [x] Placeholder trades
- [x] Cash + trade settlement
- [x] Sold online pull list
- [x] Shopify sync outbox + force sync
- [x] Verify Shopify consistency
- [x] Review & sync staging to Shopify
- [x] Collectr CSV reconciliation
- [x] CSV import
- [x] Settings (buy %, trade %, markup, rounding, shipping rules)
- [x] Dashboard KPIs + paperweight alert
- [x] Trade history + export
- [x] Show price capture
- [x] Label generation (QR/barcode)
- [x] Updated cards / needs restickering
- [x] Pokemon TCG API fetch on intake
- [x] Persistent SKU reuse across acquisitions
- [x] Local image repository (`/static/scraped_thumbnails`)

See [FEATURE_PARITY.md](./FEATURE_PARITY.md) for the full partner-feature matrix.
---

## Local Dev

Canonical workspace:

`C:\Users\Chris\Desktop\Cursor Projects\StashTab`

```powershell
docker compose up -d
cd services/api; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8001
npm run dev -- -p 3001
```

**URLs:** Landing `:3001` · POS `:3001/pos` · API docs `:8001/docs`

---

## Agent Instructions

1. Read this file, mutable current context, and only the relevant contract/role
   packet before work.
2. Map and test partner Python behavior; do not blindly copy it or rewrite it in
   TypeScript.
3. Preserve existing and legacy frontend work until F1 recovery review.
4. Multi-tenant: verified Clerk identity plus membership and `shop_id` scope.
5. Roadmap approval permits planning only. Do not push, merge, migrate, deploy,
   use paid credits, or access production without the matching human approval.

### Frozen card-resolution contract

Any work involving card identification, OCR-assisted intake, catalog matching,
JustTCG fallback, pricing enrichment, review queues, or promotion to inventory
must comply with
[`docs/card-resolution-workflow/CONTRACT.md`](./docs/card-resolution-workflow/CONTRACT.md).
The contract is frozen at version `1.0.0`; changes require its documented
amendment and approval process.

Marketplace consumer checkout is **out of product scope**. StashTab is a
vendor-only SaaS OS. POS payments, cash reconciliation, and Stripe/PayPal
**planning** live in
[`docs/security-assurance-v1/`](./docs/security-assurance-v1/). Do not
integrate Stripe/PayPal, create payment or Watch tables, or treat Phase 6
“SaaS launch DONE” as card-present or analytics go-live.

### Vendor OS product strategy

The approved positioning, existing-feature reconciliation, inventory
optimization target, USPs, and dependency-ordered roadmap live in
[`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`](./docs/product-strategy/VENDOR-OS-USP-ROADMAP.md).

Agents must inspect the current implementation before planning a roadmap slice.
Extend the existing Python inventory, staging, purchase, sales, show, pricing,
reconciliation, resticker, reporting, and Shopify systems when they provide the
stronger foundation. Do not build parallel replacements.

Roadmap approval is product direction, not implementation authority. Inventory
events/lots/locations, cash sessions, exact-money migrations, Watch data,
models, jobs, and advisory agents remain blocked until their named gates pass.

### Agent context and gated backlog

Fresh agents must use [`docs/agent-context/INDEX.md`](./docs/agent-context/INDEX.md)
instead of raw conversation history. Current gates and the next queued build phase
are maintained in that directory. A backlog entry authorizes planning only unless
its entry gate explicitly marks implementation ready.
