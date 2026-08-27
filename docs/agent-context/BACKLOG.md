# Gated build backlog

## card-resolution-core-v1

**Status:** QUEUED — PLANNING ALLOWED, BUILD BLOCKED
**Entry gate:** named human implementation unlock. Notification backend
overlap is closed (D-021). Frontend notification settings, service worker,
and live Web Push remain separate gates.

### Planned slices

1. Workflow state and audit schema with `shop_id` and idempotency constraints.
2. Versioned deterministic local candidate scoring with component evidence.
3. State-transition service and reconciliation accounting.
4. Cached, budgeted, disabled-by-default JustTCG adapter.
5. Human-review API and queue UI.
6. Transactional staging/inventory promotion after separate acceptance evidence.

### Exit evidence

All fourteen acceptance gates in contract section 13, migration review, tenant
isolation tests, reconciliation proof, and explicit human release approval.

### Automation rule

Automation may create a proposed implementation plan and review artifacts. It may
not auto-start implementation while the status contains `BUILD BLOCKED`, and it
may never enable production external calls or inventory writes without approval.

## security-assurance-v1

**Status:** QUEUED — RESEARCH AND PLANNING ALLOWED, IMPLEMENTATION BLOCKED
**Entry gate:** named human approves a listed implementation slice in
`docs/security-assurance-v1/PHASED-IMPLEMENTATION.md`. Planning docs may be
edited without that gate.

### Scope

SOC 2 readiness planning, database control design (including proposed RLS),
bounded security testing, vendor-POS payment/PCI/accounting **planning**,
tenant lifecycle, Portfolio Watch / Market Watch **contracts**, AI-risk and
governed learning, rules of engagement, and workflow liveness. Packet:
`docs/security-assurance-v1/`.

Consumer marketplace, meetup, multi-vendor cart, seller payouts, and escrow
are withdrawn. Stripe/PayPal integration, payment/Watch tables, models,
scheduled jobs, and production payment credentials remain blocked.

### Non-blocking rule

This item must not block `card-resolution-core-v1` or the notification
checkpoint merely because the SOC 2 program is unfinished. Only a separately
approved, named baseline control may become a release blocker.

### Automation rule

Agents may research and write planning documents. They must not implement
scanners, attack tools, migrations, production access, scheduled jobs,
blocking gates, Stripe/PayPal integrations, payment or Watch tables, models,
continual learning, or seller-marketplace onboarding, and must not freeze a
security contract, while the status contains `IMPLEMENTATION BLOCKED`.

## vendor-os-usp-roadmap

**Status:** APPROVED DIRECTION — PLANNING ALLOWED, IMPLEMENTATION BLOCKED
**Source:** `docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`

### Dependency order

Product-direction order from the strategy file, unchanged:

1. Current notification and contract gates.
2. `card-resolution-core-v1` identity/state foundation.
3. Inventory truth (`inventory-truth-v1` **frozen**; blocked by
   fail-closed identity, then lots/events).
4. Vendor financial operations: cash sessions and operational subledger.
5. Licensed point-in-time market-data foundation.
6. Deterministic Portfolio/Market Watch.
7. Governed advisory agents and outcome evaluation.

Current operational sequence is PLAN.md F0 then F1 (D-026): staging
identity (accepted) → inventory schema rehearsal (proposed) → inventory
truth staging proof → card-resolution core → notification staging
mechanics → minimum security/ops; then frontend recovery. This overlay
does not rewrite the strategy file or unlock implementation.

### Reuse gate

Each slice must cite the existing models, logic, APIs, UI, and tests it extends.
Creating a parallel inventory, sales, show, pricing, reconciliation, Shopify,
or Watch subsystem is blocked unless independent architecture review proves the
existing system cannot be migrated safely.

### Implementation gate

Product approval does not authorize code, migrations, external data use,
payments, scheduled jobs, model promotion, automatic repricing, or inventory
mutation. Each slice requires a reviewed plan, acceptance evidence, and named
human unlock.

## fail-closed-shop-identity-v1

**Status:** `COMPLETED — ACCEPTED 2026-08-23`
**Source:** `docs/fail-closed-shop-identity-v1/ACCEPTANCE.md`
**Unlock:** D-010. Accepted by human owner; evidence recorded in
`ACCEPTANCE.md`.

`DEPLOYMENT GATE — IDENTITY OWNER — REQUIRED BEFORE PRODUCTION SCHEMA
APPLY`: add the unique `(shop_id, clerk_user_id)` index to already-created
production databases as a controlled schema step. It does not block
isolated development, but it cannot be silently omitted from production
preparation. That index is not an inventory-truth migration.

## inventory-truth-v1 / slice-01-receive-foundation

**Status:** `COMPLETED — NOT DEPLOYED (ACCEPTED 2026-08-23)`
**Source:** `docs/inventory-truth-v1/ACCEPTANCE-SLICE-01.md`;
`docs/inventory-truth-v1/reviews/SLICE-01-PG-ACCEPTANCE.md`
**Slice id:** `slice-01-receive-foundation`

Frozen planning contract for immutable lots and inventory events under
existing `InventoryItem` / `Sale` / `PurchaseRecord`. Only the frozen
receive-foundation slice is authorized: migrator-only schema, additive
`(shop_id, id)` keys, receive dual-write on staging commit and trade
receive, idempotent backfill with the canonical key, reconciliation,
loss terminology, tests, and rollback drill.

PostgreSQL acceptance (disposable container, synthetic data): all fourteen
owner criteria pass; historical backfill produced +5/+3 receive, −5 loss
(no Sale row), zero-gap no-op; blocking CI job
`inventory-truth-gates.yml` runs the same harness without production
credentials.

Standing deployment gates: human approval before any production schema
apply; production membership unique index `(shop_id, clerk_user_id)`;
cutover reconciliation must equal zero; cutover runbook, audit logging,
and break-glass procedure.

## inventory-truth-v1 / slice-02-outbound-events

**Status:** `COMPLETED — ON main VIA c3647a4 — NOT DEPLOYED (ACCEPTED 2026-08-24)`
**Source:** `docs/inventory-truth-v1/ACCEPTANCE-SLICE-02.md`;
`docs/inventory-truth-v1/DIRECTIVE-SLICE-02.md` (v3, frozen);
`docs/inventory-truth-v1/amendments/AMENDMENT-1.1.0.md` (APPROVED)

Isolated implementation accepted 2026-08-24. Merge completed via D-021 /
PR #1. **NOTIFICATION-INTEGRATION-GATE** is closed for backend overlap only.
Production schema application remains blocked by
**MIGRATOR-ROLE-PROVISIONING-GATE** plus standing deployment gates.
Adjustment, production cutover, refund payments, manual-resolution UI,
payments, and Watch remain outside this slice.

## staging-readiness-v1 / slice-01-base-schema-and-identity-smoke

**Status:** `COMPLETED, DEPLOYED TO STAGING ONLY (ACCEPTED 2026-08-26)`
**Source:** `docs/staging-readiness-v1/ACCEPTANCE-SLICE-01.md`; D-025

Identity kernel on staging Neon (`shops`, `shop_members` only). Railway
deploy `17aeb85f-053f-4e5a-8d68-6d040d03c238`. Clerk identity smoke passed
for two synthetic shops. Production remains undeployed. Inventory schema
rehearsal is **not** unlocked.

## staging-readiness-v1 / slice-02-inventory-schema-rehearsal

**Status:** `APPROVED FOR LOCAL IMPLEMENTATION — HOSTED APPLY LOCKED`
**Source:** D-027; `docs/staging-readiness-v1/PLAN-SLICE-02-INVENTORY-SCHEMA-REHEARSAL.md`;
`docs/staging-readiness-v1/DIRECTIVE-SLICE-02-IMPLEMENTATION.md`

Owner locked the table set to `inventory_item`, `purchase_record`, and
`sale`, then inventory-truth tables. Local PostgreSQL 16 implementation
is approved. Neon stays locked. API SELECT only. Do not enable inventory
routes. Do not apply hosted schema.

## staging-readiness-v1 / slice-00-isolated-api-code

**Status:** `COMPLETED — ON main VIA LATER MERGES — STAGING API DEPLOYED FOR IDENTITY ONLY (ACCEPTED 2026-08-25)`
**Source:** `docs/staging-readiness-v1/ACCEPTANCE-SLICE-00.md`; planning
checkpoint `131bc1eed01f3e9b732e41cde039de6c15cea707`; D-023; PR #2

Isolated API safety code accepted and later merged. Staging currently
runs the identity kernel only (D-025). Production remains undeployed.
Convex is out of architecture (D-024), not a later staging item. Inventory
schema, worker, Shopify, and notifications are not unlocked.

## frontend-recovery-f1

**Status:** `QUEUED — PLANNING ALLOWED, IMPLEMENTATION BLOCKED ON F0 EXIT`
**Source:** `PLAN.md` F1; D-026

Inventory, recover, and redesign current plus preserved legacy UI after
the backend-foundation exit gate. Do not bulk-copy a dirty legacy tree
over `main`. Do not move Python logic into React or revive Convex.

## master-plan-reconciliation

**Status:** `PROPOSED — DOCS ONLY, AWAITING ACCEPTANCE`
**Source:** D-026; `PLAN.md`; `AGENTS.md`

Documentation alignment of the master plan and mutable agent context.
Does not unlock slice-02, production, payments, Watch, Web Push, worker,
or Shopify.

## backend-notification-integration-v1

**Status:** `MERGED TO main AS c3647a4 — NOT DEPLOYED`
**Source:** `docs/backend-notification-integration-v1/ACCEPTANCE-1.1.2.md`;
`AMENDMENT-1.1.1.md`; `AMENDMENT-1.1.2.md`; manifests `freezes/FREEZE-1.1.1.json`
and `FREEZE-1.1.2.json`

Local 1.1.2 backend accepted 2026-08-25. PR #1 merged as `c3647a4`.
**NOTIFICATION-INTEGRATION-GATE** is closed for backend overlap only.
**MIGRATOR-ROLE-PROVISIONING-GATE** still blocks production schema apply/deploy.
Frontend settings, service-worker install, and live Web Push remain open.

## inventory-truth-v1 / slice-03-adjustments

**Status:** `COMPLETED — ON main VIA c3647a4 — NOT DEPLOYED (ACCEPTED 2026-08-24)`
**Entry gate:** named human implementation unlock of `DIRECTIVE-SLICE-03-IMPLEMENTATION.md`.

Must cover every remaining absolute or manual inventory mutation path
(admin PATCH, CSV import, corrections, shrinkage/loss, cycle-count
variance if introduced, recovery from mistaken adjustments) and replace
silent absolute overwrites with append-only, auditable quantity changes
while preserving the existing inventory snapshot.
