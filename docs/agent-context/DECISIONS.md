# Approved decisions

## D-001 — Durable context lives in the repository

Fresh agents receive a compact role-specific packet rather than raw conversation
history. Evidence and exact commits take precedence over summaries.

## D-002 — One automation engine

Context validation, independent reviews, synthesis, and handoff proposals remain
stages of the existing GitHub workflow. A second workflow engine is unnecessary.

## D-003 — Backlog is not execution authority

A queued phase may be decomposed and reviewed, but cannot cross its listed entry
gate. Production writes, migrations, credentials, pushes, and deployments retain
their explicit human approvals.

## D-004 — Security program is not a silent card-resolution gate

Proposed 2026-08-14 from the security-assurance-v1 planning request. An
unfinished SOC 2 or security-assurance program must not block card-resolution
build. Only a separately approved, named baseline control may become a release
blocker.

## D-005 — Marketplace payment intent (WITHDRAWN)

Recorded 2026-08-14 then **withdrawn the same day**. Consumer marketplace,
meetup, multi-vendor cart, marketplace shipping, seller payouts, escrow, and
buyer protection are out of product scope.

## D-006 — Vendor-only SaaS OS and advisory Watch (proposed)

Recorded 2026-08-14. StashTab serves approved card-business tenants (POS,
inventory, intake, cash recon, payment recon, accounting support, Portfolio
Watch, Market Watch, reporting). Each vendor is merchant of record on its
own POS; StashTab does not custody funds. Watch products are advisory.
Payments, Watch, models, and schemas remain unimplemented pending human
gates.

## D-007 — Vendor OS USPs and reuse-first optimization (approved)

Approved 2026-08-14. StashTab differentiates through inventory truth,
acquisition-to-exit economics, show-floor operations, confidence-aware card
resolution, vendor Portfolio/Market Watch, accounting evidence, and
exception-first automation. Existing Python/FastAPI inventory, staging,
purchase, sales, show, pricing, reconciliation, resticker, reporting, and
Shopify foundations are extended or safely migrated; parallel replacements are
not created without independent architecture evidence. Approval records product
direction only and does not unlock implementation.

## D-008 — Receipt, lots, and electronic-tender reservation (approved)

Approved 2026-08-14.

1. One customer checkout is one transaction/receipt with one or more `Sale`
   lines. Keep existing line records. Add a compatible parent receipt
   identity. Do not replace the sales system.
2. Every acquisition is a separate immutable lot, including repeats of the
   same SKU at different costs. Keep weighted-average cost on the inventory
   snapshot. Do not merge lot history. FIFO / weighted-average / specific
   identification for COGS is deferred to accountant review and does **not**
   block capturing lots.
3. Future Stripe/PayPal: reserve inventory when electronic checkout starts;
   finalize and deduct only after a signature-verified, idempotent webhook
   confirms payment; release the reservation on failure, cancellation, or
   expiry. Cash and trade may finalize immediately after vendor confirm.

Routine schema, index, migration, backfill, event, idempotency, and test
shape is planner/reviewer work unless it changes product behavior, legal
responsibility, money handling, data-loss risk, or a frozen contract.

Deferred professional gates (not planning-package blockers): final COGS
method; trade-credit/stored-value treatment; market-data licensing; PCI
determination; Stripe/PayPal production configuration; production migration
approval.

## D-009 — Inventory truth planning contract frozen

Approved 2026-08-20. `STASHTAB-INVENTORY-TRUTH-001` v1.0.0 is frozen.
Evidence: `docs/inventory-truth-v1/reviews/FREEZE-CHECK.md` (eight
criteria PASS) and `docs/inventory-truth-v1/CONTRACT.md`.

Status: **FROZEN, IMPLEMENTATION BLOCKED BY FAIL-CLOSED IDENTITY**.
This decision does not unlock lots, events, dual-write, backfill,
migrations, authentication, payments, or Watch. Amendments require a
separately versioned proposal and cannot silently edit the frozen
bodies.

## D-010 — Fail-closed shop identity (approved)

Approved 2026-08-20; **accepted 2026-08-23** (see
`docs/fail-closed-shop-identity-v1/ACCEPTANCE.md`). Unlocked and completed
the `fail-closed-shop-identity-v1` slice only.

1. Production is `APP_ENV`. Values: `local`, `test`, `staging`,
   `production`. Missing, invalid, staging, or production never enable
   the local identity bypass. `DEBUG` alone cannot authorize a bypass.
2. Multi-shop users select an active shop in the UI. Submitted shop ID
   is an untrusted hint. FastAPI derives the user from the signed token
   and confirms membership. Mismatch or missing membership fails closed.
3. Shop create, onboard, and invite require a verified signed-in user.
   Create establishes owner membership atomically or fails without an
   accessible orphan shop. Anonymous create/invite are not allowed.
4. Named unlock: implement only this identity slice and its tests.

## D-011 — Inventory receive foundation accepted (approved)

Accepted 2026-08-23. `inventory-truth-v1 / slice-01-receive-foundation` is
**COMPLETED — NOT DEPLOYED**. Evidence:
`docs/inventory-truth-v1/ACCEPTANCE-SLICE-01.md` and
`docs/inventory-truth-v1/reviews/SLICE-01-PG-ACCEPTANCE.md` (14/14
PostgreSQL criteria on fresh disposable databases, twice; 104 SQLite
regressions; deterministic backfill; zero-mismatch reconciliation; loss
creates no Sale row; atomic idempotent migration; freeze failures
propagate; blocking credential-free CI gate).

Standing deployment gates: human approval before any production schema
apply; production membership unique index; cutover reconciliation must
equal zero; cutover runbook + audit logging + break-glass procedure.
Outbound (sell) dual-write requires a new named unlock.

## D-012 — Outbound events are the next inventory-truth slice (approved)

Approved 2026-08-23 with five planning decisions. `slice-02-outbound-events`
covers quantity-reducing paths only after a complete outbound-path
inventory. It must preserve Sale rows, weighted-average cost, POS
behaviour, and Shopify ownership.

Owner decisions (approved 2026-08-23):

1. Financial refund does not auto-restock; inventory increases only after
   vendor-confirmed whole-unit physical returns that are resalable.
2. Partial monetary refunds are independent of inventory; only confirmed
   whole-unit returns create positive quantity.
3. Refund/return records are append-only and reference the original
   sale/outbound event; history is never deleted or rewritten. Financial-
   refund execution stays outside the inventory slice unless existing
   behaviour already requires it.
4. POS rejects insufficient-stock sales; external Shopify over-sales keep
   the external sale record, write events for quantity actually removed,
   raise a critical exception preserving the shortage, alert the vendor,
   keep auto-pause, and never silently clamp to zero or fabricate full
   sells.
5. Outbound ships before adjustments; admin PATCH and CSV absolute
   overwrites remain frozen; the adjustment slice must complete before any
   production inventory-truth cutover.

Planning approval only — implementation requires a separate named unlock
AND a CONTRACT §6 amendment vote (outbound canonical keys + migration
envelope additions). After five independent planning reviews and one
bounded correction pass, the directive is at v3 with a fail-closed,
per-line observation-ledger duplicate design:
`docs/inventory-truth-v1/DIRECTIVE-SLICE-02.md` and
`reviews/SLICE-02-PLANNING-REVIEWS.md`.

## D-013 — AMENDMENT-1.1.0 approved; slice-02 plan frozen (approved)

Approved by named human vote 2026-08-23. AMENDMENT-1.1.0 applied as the
exact diff; contract `STASHTAB-INVENTORY-TRUTH-001` is now **v1.1.0**
(freeze record + SHA-256 hashes in CONTRACT §8; v1.0.0 record preserved).
Seven binding interpretations recorded in amendment §17: (1) oversale
exceptions reuse-not-stack per canonical order-line key, concurrency-safe
and idempotent; (2) observation ledger retained over a lighter index;
(3) alert routing — always in-app critical exception, Web Push only
behind existing gates plus vendor opt-in, delivery failure never resolves
the exception, SMS out of scope; (4) POS insufficient stock → 409 with
stable machine-readable code and zero partial mutation; (5) authorized
manual-resolution workflow required before production outbound cutover —
no automated similarity-based compensation until then; (6) resalable is
a vendor-owned decision with authorized staff recording actor/shop/
timestamp/original-ref/qty/outcome — only confirmed whole-unit resalable
outcomes increase inventory; (7) exception retention is a named policy
follow-up with no auto-delete default.

Bounded integrity check passed 5/5
(`reviews/AMENDMENT-1.1.0-INTEGRITY-CHECK.md`). Slice-02 plan frozen
against v1.1.0. Implementation was later unlocked, completed, and
accepted 2026-08-24 (see D-014).

## D-014 — Slice-02 outbound events accepted, not merged (approved)

Approved by named human vote 2026-08-24. `inventory-truth-v1 /
slice-02-outbound-events` is **COMPLETED, NOT MERGED, NOT DEPLOYED**.
Evidence: `docs/inventory-truth-v1/ACCEPTANCE-SLICE-02.md`.

Binding follow-up gates:

- **NOTIFICATION-INTEGRATION-GATE** blocks merge and deployment until
  slice-02 `main.py` / `worker.py` and overlapping files are reconciled with
  the preserved notification implementation and both suites pass together.
- **MIGRATOR-ROLE-PROVISIONING-GATE** blocks production schema application
  and deployment until the migrator role is deliberately provisioned,
  reviewed, non-assumable by the runtime role, credential-free in app
  config/containers, time-bounded, and audited, and runtime
  UPDATE/DELETE/TRUNCATE still fail.

Admin PATCH and CSV absolute quantity overwrites remain frozen until
`slice-03-adjustments` is separately implemented under a named unlock.

## D-015 — AMENDMENT-1.2.0 approved; contract and slice-03 plan frozen (approved)

Approved by named human vote 2026-08-24. `STASHTAB-INVENTORY-TRUTH-001`
is **v1.2.0**. Hashes live in
`docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json` (CONTRACT §9 pointer
only; CONTRACT does not store its own hash). v1.0.0 §2 and v1.1.0 §8
remain. The reviewed `DIRECTIVE-SLICE-03.md` is frozen against v1.2.0.
Implementation of slice-03 is **not** authorized. Future contract changes
require a new versioned amendment and a new freeze manifest; do not
overwrite `FREEZE-1.2.0.json`.

