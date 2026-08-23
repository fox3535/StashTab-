# Gates (closed path)

**Packet status:** `FROZEN v1.1.0 — SLICE-01 COMPLETED (ACCEPTED 2026-08-23, NOT DEPLOYED); SLICE-02 PLAN FROZEN, AWAITING IMPLEMENTATION APPROVAL`

This packet does **not** implement fail-closed identity.

## Planning path (this wording pass)

| State / gate | Owner | Evidence | Deadline / attempts | Terminal |
|---|---|---|---|---|
| `CORRECTION_IN_PROGRESS` | Planner | Locked wording covering the eight freeze criteria | This authorized pass only (1) | → `READY_FOR_FREEZE_CHECK` |
| `READY_FOR_FREEZE_CHECK` | Freeze-check reviewer ≠ planner | Pass/fail on the eight criteria only; no redesign | 1 attempt | Pass → status `READY FOR FREEZE APPROVAL`. Fail → `REJECTED — OWNER ACTION REQUIRED` |
| Freeze decision | Executive sponsor | `reviews/FREEZE-CHECK.md` plus human freeze 2026-08-20 | Closed | **`FROZEN`** (`CONTRACT.md` v1.0.0) |

Timeout is never success. A failed freeze check does **not** start another
review loop; it names the failed criterion and owner and **stops**.

## After freeze (not this pass)

| Gate | Owner | Evidence | Deadline / attempts | Terminal |
|---|---|---|---|---|
| Fail-closed identity (`identity-fail-closed`) | Control owner — Identity | Verified JWT + explicit shop membership; header shop-id and header user-id rejected on inventory mutations and membership writes | Separate slice; 1 unlock | **`completed`** (accepted 2026-08-23; `docs/fail-closed-shop-identity-v1/ACCEPTANCE.md`) |
| `implementation_unlock` `inventory-truth-foundation` | Executive sponsor | Packet `FROZEN`; identity slice `completed`; TESTS.md on the PR | 14 days | **Executed 2026-08-23**: slice-01 implemented, reviewed, corrected, PG-verified |
| Human acceptance of `slice-01-receive-foundation` | Human owner | `reviews/SLICE-01-PG-ACCEPTANCE.md` (14/14 pass ×2 fresh DBs); 104 SQLite regressions; atomic+idempotent migration; blocking credential-free CI gate | Closed | **`COMPLETED — ACCEPTED 2026-08-23`** (`ACCEPTANCE-SLICE-01.md`) |
| Schema apply (contract §12.8) | Executive sponsor | Approved migrator plan; `create_all` acceptance check green; PG harness green | When apply is about to run; 1 | **STILL OPEN — blocks production schema application** |
| Production migration | Executive sponsor | Deferred professional gate | n/a | Not a planning blocker |

## Standing deployment gates (recorded at slice-01 acceptance)

1. Human approval before any production schema application.
2. Production membership unique index `(shop_id, clerk_user_id)`.
3. Cutover reconciliation must equal zero (timeout is not green).
4. Cutover operations runbook, audit logging, and break-glass procedure.

## Slice-02 (`slice-02-outbound-events`)

| Gate | Owner | Evidence | Terminal |
|---|---|---|---|
| Planning approval of `DIRECTIVE-SLICE-02.md` | Human owner | Directive with complete outbound-path inventory and boundaries | **APPROVED 2026-08-23** (D-012, five decisions) |
| Independent planning reviews (5) | Reviewers ≠ planner | Architecture, Data-integrity, Database-security, Adversarial/concurrency, Workflow-liveness — `reviews/SLICE-02-PLANNING-REVIEWS.md` | **Complete; one bounded correction pass applied → v3** |
| CONTRACT §6 amendment vote (outbound keys + migration envelope) | Executive sponsor | `amendments/AMENDMENT-1.1.0.md` — **APPROVED 2026-08-23**, applied as exact diff; contract v1.1.0 (CONTRACT §8 hashes); integrity check 5/5 `reviews/AMENDMENT-1.1.0-INTEGRITY-CHECK.md` | Closed |
| Freeze decision for slice-02 plan | Human owner | v3 directive + reviews + amendment + integrity check | **`FROZEN` 2026-08-23 against contract v1.1.0** |
| `implementation_unlock` slice-02-outbound-events | Executive sponsor | Directive prepared, NOT executed: `DIRECTIVE-SLICE-02-IMPLEMENTATION.md` | Pending named human approval |
| Manual-resolution workflow (duplicate suspicions) | Separate named unlock | Required BEFORE production outbound cutover; no automated similarity compensation until it exists | Open gate |
| Adjust-slice completion | Separate named unlock | Required BEFORE production inventory-truth cutover (owner decision 5) | Open gate |
| Critical-exception retention policy | Operations/policy follow-up | No auto-delete of unresolved exceptions or audit history until a policy exists | Open follow-up |

## Deferred professional gates (not planning / freeze blockers)

COGS method; trade-credit booking; market-data license; PCI; Stripe/PayPal
production config; production migration approval.

## Not this slice

Payments capture, Watch, receipt parent, RLS, POS reservation behaviour,
removing `create_all` for **existing** models, identity implementation.
