# Gated build backlog

## card-resolution-core-v1

**Status:** QUEUED — PLANNING ALLOWED, BUILD BLOCKED
**Entry gate:** current notification/checkpoint PR passes automated tests,
independent reviews are resolved, and a human approves build start.

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

1. Current notification and contract gates.
2. `card-resolution-core-v1` identity/state foundation.
3. Inventory truth (`inventory-truth-v1` **frozen**; blocked by
   fail-closed identity, then lots/events).
4. Vendor financial operations: cash sessions and operational subledger.
5. Licensed point-in-time market-data foundation.
6. Deterministic Portfolio/Market Watch.
7. Governed advisory agents and outcome evaluation.

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

**Status:** `COMPLETED — NOT MERGED — NOT DEPLOYED (ACCEPTED 2026-08-24)`
**Source:** `docs/inventory-truth-v1/ACCEPTANCE-SLICE-02.md`;
`docs/inventory-truth-v1/DIRECTIVE-SLICE-02.md` (v3, frozen);
`docs/inventory-truth-v1/amendments/AMENDMENT-1.1.0.md` (APPROVED)

Isolated implementation accepted 2026-08-24. Merge and deployment remain
blocked by **NOTIFICATION-INTEGRATION-GATE**. Production schema application
remains blocked by **MIGRATOR-ROLE-PROVISIONING-GATE** plus standing
deployment gates. Adjustment, production cutover, refund payments,
manual-resolution UI, payments, and Watch remain outside this slice.

## inventory-truth-v1 / slice-03-adjustments

**Status:** `PLAN FROZEN against v1.2.0 — IMPLEMENTATION BLOCKED`
**Entry gate:** named human implementation unlock of `DIRECTIVE-SLICE-03-IMPLEMENTATION.md`.

Must cover every remaining absolute or manual inventory mutation path
(admin PATCH, CSV import, corrections, shrinkage/loss, cycle-count
variance if introduced, recovery from mistaken adjustments) and replace
silent absolute overwrites with append-only, auditable quantity changes
while preserving the existing inventory snapshot.
