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
Merge status later superseded by D-021; the code is on `main` via
`c3647a4` and remains not deployed.

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
Implementation of slice-03 was later unlocked and accepted (D-016). Future contract changes
require a new versioned amendment and a new freeze manifest; do not
overwrite `FREEZE-1.2.0.json`.

## D-016 — Slice-03 adjustments accepted, not merged (approved)

Approved by named human vote 2026-08-24. `inventory-truth-v1 /
slice-03-adjustments` is **COMPLETED, NOT MERGED, NOT DEPLOYED**.
Evidence: `docs/inventory-truth-v1/ACCEPTANCE-SLICE-03.md`.
Merge status later superseded by D-021; the code is on `main` via
`c3647a4` and remains not deployed.

CSV cost fields on existing items remain unapplied. **CSV-COST-FEEDBACK-GATE**
blocks production CSV adjust use until the API/import result and eventual
interface explicitly report ignored cost fields and point to a separately
approved cost-correction workflow.

## D-017 — Notification AMENDMENT-1.1.1 approved and frozen (approved)

Approved by named human vote 2026-08-24. `STASHTAB-CARD-RESOLUTION-001 /
AMENDMENT-1.1.1` is **FROZEN**. AMENDMENT-1.1.0 remains the unchanged
product-policy record. Hashes live in
`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`.

Binding transport interpretation (D-N5): Web Push is at-least-once where
provider acknowledgement cannot be atomic with local `sent`. A crash
after provider success may cause a safe duplicate. Payloads and click
actions must be idempotent and non-mutating. Duplicate delivery cannot
alter inventory, adjustment, card-resolution, or security events.
Exactly-once is not claimed. Retry and transport outcome are audited.

Backend implementation is **not** authorized until a named unlock of
`DIRECTIVE-IMPLEMENTATION.md`. Frontend, production VAPID, live push,
migrations, merge, and deploy remain blocked.

## D-018 — Notification AMENDMENT-1.1.2 approved and frozen (approved)

Approved by named human vote 2026-08-24. `STASHTAB-CARD-RESOLUTION-001 /
AMENDMENT-1.1.2` is **FROZEN**. AMENDMENT-1.1.0 and AMENDMENT-1.1.1 remain
unchanged. Hashes live in
`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`.

Additive schema: `notification_source_observation`,
`notification_occurrence_transition`, `notification_delivery_attempt`,
`notification_recovery_park`; event `occurrence_count` and `last_seen_at`;
delivery `claimed_until` and `UNIQUE (shop_id, id)`. Inventory is 8 frozen
plus 4 new = 12 tables.

Backend implementation is **not** authorized until a new named unlock of
`DIRECTIVE-IMPLEMENTATION.md` covering 1.1.0+1.1.1+1.1.2. The 1.1.1 unlock
does not authorize 1.1.2 apply. Frontend, production VAPID, live push,
migrations, merge, and deploy remain blocked.

## D-019 — Notification 1.1.2 backend accepted locally (approved)

Approved by named human owner 2026-08-25.
`backend-notification-integration-v1 / implementation-1.1.2` is
**COMPLETED — NOT PUSHED — NOT MERGED — NOT DEPLOYED**. Evidence is in
`docs/backend-notification-integration-v1/ACCEPTANCE-1.1.2.md`.
Push/merge status later superseded by D-021; the code is on `main` via
`c3647a4` and remains not deployed.

Merge and deployment now require **GITHUB-NOTIFICATION-CI-GATE**: the blocking
PostgreSQL notification workflow must execute successfully on GitHub against
the exact pushed commits. The unexecuted workflow definition is not execution
evidence. Production VAPID, live Web Push, production schema apply, frontend
settings, and service-worker install remain blocked.

## D-020 — Draft foundation PR and backend overlap review (approved)

Approved by named human owner 2026-08-25. Keep draft PR #1 as one foundation
PR; do not split or rewrite history. Head `4d317f8` required GitHub CI passed.
Backend notification overlap integration review passed.
**NOTIFICATION-INTEGRATION-GATE** is closed for backend overlap only.
Remaining open gates: frontend notification settings/service worker;
frontend authenticated API transport; production VAPID/live Web Push;
production migration/roles/cutover. **CSV-COST-FEEDBACK-GATE** stays open.
The PR stays draft, unmerged, and undeployed.

## D-021 — Foundation PR #1 merged, not deployed (approved)

Approved by named human owner. PR #1 merged to `main` as
`c3647a4eda37d355ed47f9e77ad667e4fda7930c`. **Not deployed.** D-020’s
“keep draft / do not merge” is superseded for merge status only. Production
schema, VAPID, and live Web Push remain blocked.

## D-022 — Staging owner decisions (approved)

Approved by named human owner 2026-08-25. Slice 0: separate Railway API
project, separate Neon, dedicated Clerk; worker later in that Railway
project under a separate unlock; Vercel and Convex deferred. No shared
production database, credentials, Clerk tenant, or secrets. Synthetic
data only; no production clone. No Shopify in slice 0; missing
settings/tokens mean sync off. Neon owner runs reviewed role SQL; runtime
cannot create roles or assume migrator. Chris is initial incident owner
and break-glass approver; a second qualified human is required before
production. First boot: `APP_ENV=staging`, debug off, bypass off,
notifications off, no VAPID, worker not running, Shopify absent, inventory
cutover off, no production credentials. Never run local seed against
staging. Details: `docs/staging-readiness-v1/OWNER-DECISIONS.md`.

## D-025 — Staging slice-01 identity smoke accepted on staging only (approved)

Approved by named human owner 2026-08-26.
`staging-readiness-v1 / slice-01-base-schema-and-identity-smoke` is
**COMPLETED, DEPLOYED TO STAGING ONLY**. Railway API deploy
`17aeb85f-053f-4e5a-8d68-6d040d03c238` at Git SHA
`0dd8f00b8d510b82e3d717a9570c0bc387e0479b`. Current `main` is
`fe3b2cfb9903050eef45bcf434ef8a0ddafdb3e8`. Neon has only `shops` and
`shop_members`, plus two synthetic shops with two distinct Clerk owners.
Identity smoke: anonymous and spoofed-header requests rejected; shop and
owner membership committed together; duplicate slug rejected; user A and
user B own-shop 200 / other-shop 403; duplicate membership 409 without
database detail; health and ready 200. No Shopify, inventory, notifications,
worker, Web Push, payments, or production activity. Convex remains out
under D-024. Frozen `GATES.md` was not rewritten; see
`docs/staging-readiness-v1/GATES-POINTER-SLICE-01.md`.
`slice-02-inventory-schema-rehearsal` is planning only and is not unlocked.
Details: `docs/staging-readiness-v1/ACCEPTANCE-SLICE-01.md`.

## D-024 — Convex removed from the target architecture (approved)

Approved by named human owner 2026-08-26. Convex is not part of StashTab.
Identity is Clerk. FastAPI owns business logic and authorization. Neon is
the application database. Railway hosts the API and later the worker.
This supersedes earlier “Convex deferred / later Convex staging” language
in frozen staging packets (`docs/staging-readiness-v1/`, including
OWNER-DECISIONS D-022). Those files stay frozen; do not provision Convex.
Do not mirror Clerk users into Neon for this change. Clerk Protect and
the Clerk pricing table remain as a billing shell only; no payment,
payment-attempt, or webhook replacement is added. Implementation is a
frontend/docs PR only. FastAPI, Neon schema, and Railway are unchanged.

## D-023 — Staging slice-00 isolated API code accepted (approved)

Approved by named human owner 2026-08-25.
`staging-readiness-v1 / slice-00-isolated-api-code` is **COMPLETED, NOT
MERGED, NOT DEPLOYED**. Planning checkpoint
`131bc1eed01f3e9b732e41cde039de6c15cea707`. Evidence: separate liveness and
readiness; staging/production startup DDL disabled; local/test-only named
legacy bootstrap; notifications, Web Push, cutover, worker, and Shopify
default off; missing Shopify configuration skips rather than auto-enables;
development seed rejects staging/production; controlled `503 FEATURE_NOT_READY`;
SQLite 192 passed with 46 PostgreSQL-only skipped; disposable PostgreSQL 46
passed; frontend typecheck and frozen validators passed; stock/CSV freeze
response correction passed. Cloud provisioning still requires a later named
unlock. Details: `docs/staging-readiness-v1/ACCEPTANCE-SLICE-00.md`.
Merge status later superseded by PR #2 and later `main` history; staging
now runs the identity-only API in D-025. Production remains undeployed.

## D-026 — Master plan and agent context reconciled (approved)

Approved by named human owner 2026-08-26 as documentation alignment.
Canonical workspace is `C:\Users\Chris\Desktop\Cursor Projects\StashTab`.
`PLAN.md` honest capability status and F0–F4 sequence are the current
operational plan. They do not rewrite frozen contracts or
`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`. F0 is current: staging
identity is accepted; next proposed work is inventory schema rehearsal.
F1 frontend recovery starts only after the recorded F0 exit gate.
Partner Python is `vendor/mimir-partner/`; cite source, preserve behavior,
and test; do not copy blindly or rewrite it in TypeScript. Existing and
legacy frontend work is preserved; do not bulk-overwrite `main`. Convex
stays out (D-024). Agents load only the frozen contract for the subsystem
being changed. This decision does not unlock slice-02, production,
payments, Watch, live Web Push, worker, Shopify, migrations, or deploy.
The PR stays draft until acceptance.

## D-027 — Inventory rehearsal table set and privileges (approved)

Approved by named human owner 2026-08-26. Binding interpretation for
`staging-readiness-v1 / slice-02-inventory-schema-rehearsal`:

1. A separate explicit live/base schema migrator must precede
   inventory-truth DDL.
2. Do not create all remaining live application tables.
3. Create only `inventory_item`, `purchase_record`, and `sale`. Add
   another table only when a current foreign-key dependency makes it
   unavoidable. Each added dependency must be cited by model, column,
   constraint, and test. Convenience is not a dependency.
4. Add verified `shop_id → shops.id` foreign keys and the shop-scoped
   unique keys required by the frozen same-shop design.
5. First execution proof is disposable local PostgreSQL 16 only. Neon
   remains locked.
6. API receives SELECT only on rehearsal tables. No INSERT, UPDATE,
   DELETE, TRUNCATE, DDL, ownership, or migrator membership. Worker and
   readonly receive no access to those tables.
7. Rollback preserves `shops`, `shop_members`, database roles, and
   identity rows. Receive, POS, adjust, CSV quantity, Shopify, worker,
   notifications, Web Push, payments, Watch, and production remain
   unavailable.

Creating all remaining live tables is rejected: this slice proves the
inventory-truth parent chain only. Packet:
`docs/staging-readiness-v1/PLAN-SLICE-02-INVENTORY-SCHEMA-REHEARSAL.md`.
Local implementation was later approved, merged as PR #12, and applied to
staging Neon (D-028).

## D-028 — Staging inventory schema apply accepted (approved)

Approved by named human owner 2026-08-27 from verified staging evidence.
`staging-readiness-v1 / slice-02-inventory-schema-rehearsal` is
**COMPLETED, APPLIED TO STAGING ONLY**. Code on `main` is
`d49eca9fc31298847bd07abf42347ab691b4f974`. Neon `stashtab_staging` has
exactly 13 public tables: identity `shops` and `shop_members`; live
`inventory_item`, `purchase_record`, `sale`; truth `acquisition_lot`,
`inventory_event`, `inventory_truth_cutover`,
`inventory_channel_observation`, `refund_record`, `return_record`,
`inventory_exception`, `inventory_adjustment`. Both migrators were
idempotent. New tables are owned by `stashtab_migrator`. `stashtab_api`
has SELECT only. Worker, readonly, and PUBLIC have no privileges on the
new tables. Cross-shop lot insert failed. Two shops and two owners
unchanged. Inventory tables empty. Rollback not required. Railway was not
contacted. Inventory, intake, POS, adjust, CSV, Shopify, worker,
notifications, payments, Watch, and production remain off.
Details: `docs/staging-readiness-v1/ACCEPTANCE-SLICE-02.md`.
Next proposed checkpoint was read-only search. That smoke later executed
and was accepted as D-029.

## D-029 — Staging authenticated inventory read smoke accepted (approved)

Approved by named human owner 2026-08-27 from verified staging evidence.
`staging-readiness-v1 / slice-03-authenticated-inventory-read-smoke` is
**COMPLETED, STAGING ONLY**. Staging API SHA
`0dd8f00b8d510b82e3d717a9570c0bc387e0479b`. Health and ready 200. Exact
13-table set. Inventory tables empty. API SELECT allowed and INSERT
denied. Worker/readonly grants rest on D-028 because they were not
visible to `stashtab_api`. No token and spoofed headers 401. Each owner
200 empty on own shop. Cross-shop 403. CSV quantity controlled 503.
PATCH and checkout write guards were not fully proven (no item/SKU).
Intake unused because its extra live table is absent. No data changed;
background and external features stayed off.
Details: `docs/staging-readiness-v1/ACCEPTANCE-SLICE-03.md`.
PATCH, checkout, and intake remain future write-enablement gates. Do not
seed to finish them.
Planning for the next checkpoint was later approved as D-030.
Implementation remains locked.

## D-030 — Card-resolution intake/abstention planning approved

Approved by named human owner 2026-08-27 as **planning only**.
Slice `card-resolution-core-v1 / slice-01-intake-abstention`. Packet:
`docs/card-resolution-workflow/PLAN-SLICE-01-INTAKE-ABSTENTION.md`.
Pinned `main` `d49eca9fc31298847bd07abf42347ab691b4f974`.

This does **not** unlock implementation, staging DDL, JustTCG, credits,
inventory writes, or promotion of resolved cards. Existing
`/admin/intake/lookup` and `/admin/intake/staging` stay unused for this
slice. Identity `accepted` is not inventory commit.
Correction/review: `docs/card-resolution-workflow/reviews/SLICE-01-PLAN-REVIEW.md`.

## D-031 — Partner brain snapshot retained; no unlicensed port

Approved by named human owner 2026-08-27.

1. Keep `vendor/mimir-partner/` at existing `b798bf0`.
2. Do not copy or port upstream code until a license or written permission
   is recorded.
3. Upstream `df280478f09a179fcffb1842d89bcf8f1d86e03b` is **audited
   reference only**.
4. Upstream TCGCSV and JustTCG work is catalog pricing/variants, not a
   safe identity-resolution fallback.
5. RapidFuzz ≥80 is **not** verified identity.
6. FastAPI, shop scope, abstention, human review, and inventory gates stay
   StashTab’s authority. Do not replace them with upstream behavior.
7. Python snapshot refresh is deferred until permission/license is recorded.
8. TCGCSV and JustTCG adapters are deferred to later market-data/provider
   slices. JustTCG stays disabled; no credits.

Evidence: `docs/card-resolution-workflow/PARTNER-BRAIN-AUDIT-2026-08-27.md`.
Scoring-policy work may resume; implementation remains locked.

## D-032 — Intake identity scoring policy (owner-recorded, not contract-frozen)

Approved by named human owner 2026-08-27 as scoring policy for
`card-resolution-core-v1 / slice-01-intake-abstention`. Does **not** freeze
the contract or unlock implementation.

1. Required winner margin is 0.10.
2. Omitted printing always abstains.
3. A named printing may make other printings ineligible only through an
   explicit, versioned canonical printing map—not fuzzy text, price, or
   inference.
4. Diagnostic weights: game 0.15, set 0.20, collector number 0.20,
   normalized name 0.25, language 0.10, printing 0.10.
5. Initial allowed-game registry is Pokémon only.
6. Caller must supply game. Missing or unsupported game is rejected; no
   silent Pokémon default.
7. Auto-accept requires all six mandatory fields present and exact, total
   score 1.00, exactly one eligible canonical identity, and margin ≥ 0.10.
8. If two database records match all six fields, abstain (duplicate or
   ambiguous canonical identity).
9. The weighted score is diagnostic and auditable. It cannot fill in a
   missing or conflicting mandatory field.
10. Normalization for name, set, collector number, language, and printing
    is explicit and versioned. It may standardize formatting only; it must
    not treat fuzzy similarity as equality.
11. Margin is `winner_score - runner_up_score >= 0.10`. Use integer
    hundredths to avoid float ties.
12. Price and market data stay out of identity eligibility and scoring.

Packet: `docs/card-resolution-workflow/SCORING-POLICY-INTAKE-ABSTENTION.md`.
Policy freeze applied as D-033 (`identity-score-v0`). Contract remains 1.0.0.
Implementation remains locked.

## D-033 — identity-score-v0 frozen under contract §16

Approved by named human owner 2026-08-27.

`identity-score-v0` is frozen **policy detail** under
`STASHTAB-CARD-RESOLUTION-001` v1.0.0 §16. No contract amendment.
Manifest `docs/card-resolution-workflow/freezes/FREEZE-IDENTITY-SCORE-v0.json`
does not hash itself.

Locked: D-032 integer formula, six mandatory fields, `norm-v0` maps,
Pokémon-only registry, exact-match accept at 100, margin 10 hundredths,
accept/abstain/reject outcomes.

Contract §§1, 5, 6, 7, 8, 13.1, 15 already authorize unique exact local
accept without an external request. The earlier planning remark about an
amendment applied only to **ambiguous-band** auto-accept without JustTCG.

This freeze does **not** unlock implementation, staging/production schema,
external APIs, JustTCG credits, TCGCSV ingest, inventory writes, AI
identity confidence, fuzzy auto-accept, extra games, or
notification/frontend work.

## D-034 — local intake/abstention accepted, not merged, not deployed

Approved by named human owner 2026-08-27.

`card-resolution-core-v1 / intake-abstention-local-v0` is **accepted
locally** as `COMPLETED — NOT MERGED — NOT DEPLOYED — FEATURE OFF`.

Evidence: 242 SQLite/API tests; 14 scoring and 16 HTTP tests; card-
resolution PostgreSQL 16 passed twice on fresh containers (3 tests);
live-schema rehearsal 15; inventory-truth and notification PostgreSQL 46;
306 unique tests plus the three-test clean rerun. Freeze, contract,
context, compile, secret, and artifact checks passed. Six migrator-owned
tables only. Runtime grants and append-only enforcement verified.
Shop-scoped references and cross-shop denial verified. Intake/review
concurrency serialized. No provider or model path. No inventory or
pricing mutation. Rollback preserves identity and all 13 rehearsal
tables. Staging and production remain fail-closed.

An earlier combined PostgreSQL invocation failed because rehearsal ran
under the wrong role and older suites targeted an unavailable port. That
is superseded harness evidence, not a product defect. Keep the record.

Local acceptance did **not** by itself authorize merge. Merge was later
approved separately and completed as PR #13 into `main`
`6a266b10639df2931e1bd37d4040b49a0efd0bd2`. Feature remains off. Staging
and production schema and flags remain off.

Evidence: `docs/card-resolution-workflow/ACCEPTANCE-SLICE-01-INTAKE-ABSTENTION.md`.

## D-035 — F0 exit passed for frontend recovery

Approved by named human owner 2026-08-27.

`BACKEND FOUNDATION EXIT — PASSED FOR FRONTEND RECOVERY` on `main`
`6a266b10639df2931e1bd37d4040b49a0efd0bd2`.

This is not production approval. It does not enable inventory writes,
notifications, Shopify, payments, Watch, workers, or Web Push.

Satisfied for frontend recovery: staging identity isolation (D-025);
inventory schema and authenticated read smoke (D-028, D-029);
card-resolution intake/abstention merged and off (D-034); notification
isolation proven locally/PostgreSQL; no open foundation P0/P1 blocking
read-only UI work; Clerk + FastAPI header contracts exist.

Later enablement, not F0 blockers: hosted inventory write smoke,
notification staging apply, production restore drill.

Evidence: `docs/staging-readiness-v1/ACCEPTANCE-F0-EXIT.md`.

## D-036 — F1 slice-01 owner decisions

Approved by named human owner 2026-08-27.

First frontend slice is authenticated shell plus read-only inventory
search. FastAPI membership is shop authority. Stored shop ID is a
preference only. One membership auto-selects; several show a selector;
stale preference is discarded. No caller user headers. No silent
development shop fallback. Explicit sign-out on desktop and mobile.
Landing stays public. Shopify, POS sell, intake commit, resticker, CSV
quantity, notification settings/service worker, payments, and Watch
stay deferred and visibly not-ready.

Does not start implementation, deploy, or enable writes.

Evidence: `docs/frontend-recovery-v1/OWNER-DECISIONS.md`.

## D-037 — my-shop memberships read merged on main

Approved by named human owner 2026-08-27.

`frontend-recovery-v1 / prerequisite-my-shop-memberships-read-v1` is
**MERGED ON `main` via PR #15 — NOT DEPLOYED**.
Merge commit `af72bac501cd9c42b70cd0347f778db388c8c943`.

`GET /api/v1/shops/me/memberships` lists the verified Clerk user’s shops
as `{id, name, role}` only. Bearer token is required. Shop headers cannot
change the set. Empty memberships return `200` with an empty list.
`GET /api/v1/shops/me` is unchanged. No schema or writes. Frontend
slice-01 stays locked.

Evidence: `docs/frontend-recovery-v1/ACCEPTANCE-PREREQUISITE-MY-SHOP-MEMBERSHIPS.md`.

## D-038 — F1 slice-01 authenticated shell accepted locally

Approved by named human owner 2026-08-27.

`frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`
is **COMPLETED LOCALLY — NOT MERGED — NOT DEPLOYED — LIVE STAGING SMOKE
PENDING**.

Shop authority is memberships. Stored shop ID is preference only.
Inventory is read-only. Deferred tools stay not-ready. Public landing
stays public. No Convex/Svix and no backend contract change.

Later staging-smoke gates, not local blockers: real Clerk membership
loading, live staging inventory read, full authenticated-shell keyboard
walkthrough. These gates were later closed by D-039.

Evidence: `docs/frontend-recovery-v1/ACCEPTANCE-SLICE-01-AUTHENTICATED-SHELL-READ-INVENTORY.md`.

## D-039 — F1 slice-01 accepted: merged and staging smoke passed

Approved by named human owner 2026-08-27.

`frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`
is **ACCEPTED — MERGED ON `main` — STAGING SMOKE PASSED — FRONTEND NOT
DEPLOYED**.

Recorded facts: frontend code merged on `main` `3c3ca33`; staging API
deploy `9c47945a`; frontend tested locally at `http://localhost:3001`,
not deployed; real Clerk membership loaded; Smoke Shop B auto-selected;
read-only inventory returned an honest empty state; sign-out and
re-sign-in passed; keyboard and mobile checks passed; deferred features
remained locked; no schema or data writes occurred.

Bare `/admin/shopify` 404 is recorded as a non-blocking UX backlog item
(no visible navigation links to it); it becomes an honest Not Ready route
in a later navigation/deferred-routes cleanup.

This does not approve frontend deploy, writes, Shopify, notifications,
payments, Watch, or production.

Evidence: `docs/frontend-recovery-v1/ACCEPTANCE-SLICE-01-AUTHENTICATED-SHELL-READ-INVENTORY.md`.

## D-040 — F2 slice-01 controlled receive implemented locally

Approved by named human owner 2026-08-31.

`inventory-truth-v1 / f2-slice-01-controlled-receive` is **IMPLEMENTED
LOCALLY — NOT MERGED — NOT DEPLOYED — PRIVILEGES/CUTOVER UNCHANGED**.

Branch `implementation/f2-slice-01-controlled-receive`: implementation
`af9431b`, correction `feb94d6` (PostgreSQL 16 column-scoped UPDATE
grant). Local disposable PostgreSQL 16 acceptance green (F2 12, identity
12, rehearsal 15, inventory-truth PG 25, notification PG 21; clean-main
baseline 73). F2 SQLite 18; broader SQLite/API 263. Controlled 503 handler
maps only SQLSTATE 42501 / missing-relation programming errors. No staging
schema apply, privilege cutover, deploy, or cloud contact.

Evidence: `docs/inventory-truth-v1/ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`.

## D-041 — F2 slice-01 controlled receive merged on main

Approved by named human owner 2026-09-04.

`inventory-truth-v1 / f2-slice-01-controlled-receive` is **MERGED ON
`main` — NOT DEPLOYED — PRIVILEGES/CUTOVER UNCHANGED**.

PR #31 merged with a merge commit `a354fed0570241894b6e866e9e18ffbb059add6f`.
Head was `8fa58cb`; base was protected `main` `9870468`. Owner accepted
the non-blocking freeze baseline: `FREEZE-1.3.0.json` is historical
machine-byte evidence; `FREEZE-1.3.0-git-canonical.json` is the
authoritative CI record; neither frozen manifest was modified.

Staging provisioning is prepared and not executed. Cutover and receive
endpoint use remain separately locked. No Railway/Neon/Clerk contact,
migration, privilege change, or staging write.

Evidence: `docs/inventory-truth-v1/ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`;
`docs/inventory-truth-v1/CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`.

## D-042 — F2 staging provisioning reconciled and verified; API deployment checkpoint prepared

Approved by named human owner 2026-09-04.

`inventory-truth-v1 / f2-slice-01-controlled-receive` staging provisioning is
**APPLIED ON STAGING — RECONCILED AND VERIFIED — NOT DEPLOYED — CUTOVER
LOCKED**.

The provisioning prepared in D-041 was applied on Neon `stashtab_staging` only
during an **authorized Cursor run** that was interrupted (usage limit) before it
reported. This is reconciliation of an authorized action, **not** a governance
incident. Qoder verified the live state read-only against the checkpoint; every
item matched.

Recorded facts: column `purchase_record.client_idempotency_key` `varchar(36)`
nullable and partial unique index `uq_purchase_record_shop_client_key` present;
the `stashtab_api` envelope is SELECT + INSERT on the four envelope tables with
column-scoped `UPDATE (stock, cost)` on `inventory_item` only, no table-wide
UPDATE/DELETE/TRUNCATE, and USAGE on the four F2 sequences; the other seven
rehearsal tables stay SELECT-only; `stashtab_worker`, `stashtab_readonly`, and
PUBLIC hold no envelope rights and no role can assume `stashtab_migrator`; all
F2 objects are owned by `stashtab_migrator`. Every business/truth table holds
`0` rows; identity is intact at `2` shops / `2` owners; `F2-TEST-0001` is
absent; the cutover rowcount is `0` (OFF). No receive call and no partial
business-data write occurred.

A single idempotent `apply-f2-receive` returned `columns: []`, `indexes: []` and
re-affirmed grants; before/after read-only snapshots were byte-identical
(SHA-256 `c5f5eafb196d85a47fe56062c5472245de2831cfd1c90cc456c368ef7e7f087b`).
No rollback ran. The staging migrator URL file was securely destroyed after
verification. No deployment, seed, receive, cutover, or production action and no
Railway/Neon/Clerk contact occurred.

Two **pre-existing non-F2** privilege observations were recorded as follow-ups,
not F2 claims: runtime `stashtab_api` INSERT on identity `shops`/`shop_members`,
and USAGE/SELECT/UPDATE on the non-F2 truth sequences while those tables stay
SELECT-only.

An **API-only** Railway staging deployment checkpoint was prepared (not
executed): deploy protected `main` at the eventual docs-merge SHA, autodeploy
off, API service only (no worker), existing staging environment and pooled
`stashtab_api` role, cutover off, no feature flags/Shopify/notifications/Web
Push/worker jobs; after deploy verify health and ready 200, unauthenticated
receive 401, authenticated receive blocked with a controlled 503 before any
write, and Neon row counts unchanged. This decision does **not** authorize that
deployment, cutover, or any receive use.

Evidence: `docs/inventory-truth-v1/CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`;
`docs/inventory-truth-v1/ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`;
`docs/inventory-truth-v1/GATES-POINTER-F2-SLICE-01.md`;
`docs/inventory-truth-v1/CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`.

