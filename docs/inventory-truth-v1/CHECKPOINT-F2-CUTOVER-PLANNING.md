# Checkpoint — F2 cutover planning (planning only)

**Status:** `PREPARED — PLANNING ONLY — NOT APPROVED — NOT EXECUTED`
**Operations plan:** `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` (also planning
only; awaiting owner decisions)
**Slice:** `inventory-truth-v1 / f2-slice-01-controlled-receive`
**Prepared on:** `docs/f2-pre-cutover-deployment-verified` from `main` at `ec9f72c`
**Prepared:** 2026-09-04 (D-043)
**Bound by:** DIRECTIVE-F2 / AMENDMENT-1.3.0; frozen `GATES.md` §“Standing
deployment gates” and §“F2 slice-01”
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

This checkpoint **plans** the next gate. It does not approve, schedule, or
execute cutover, and it does not unlock the receive endpoint. The endpoint is
currently **deployed but fail-closed** on staging; a successful receive remains
separately locked.

## Preconditions already satisfied (verified 2026-09-04)

| # | Precondition | Evidence |
| --- | --- | --- |
| 1 | F2 controlled-receive code merged on protected `main` | PR #31 merge `a354fed`; `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md` |
| 2 | Staging provisioning applied and verified (column, partial unique index, least-privilege envelope) | `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`; D-042 |
| 3 | API-only staging deployment executed once and verified | Railway deployment `44317623` of `main` at `ec9f72c`; `CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`; D-043 |
| 4 | Fail-closed behaviour proven in the live staging runtime | unauthenticated receive `401`; exactly one authenticated probe `503` `FEATURE_NOT_READY` after membership resolution and before any write |
| 5 | Zero-write baseline recorded for later reconciliation | row-count digest `7f92454515ec31678e05a1da695f1bb02ddba0b7f67a648db008566b22d066c9`; all business/truth tables `0`; cutover rowcount `0`; both probe markers absent |
| 6 | Autodeploy off and no inactive services running | `watchPatterns: []`; one API service instance; no worker; `cronSchedule` null; all feature flags `false` |

## Preconditions still open (each must be dispositioned before execution)

Staging-scope blockers for a gen-1 synthetic-shop cutover:

1. **Cutover operations runbook, audit logging, and break-glass procedure**
   (frozen `GATES.md` standing deployment gate 4). A **planning-only draft** now
   exists — `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` — but it still requires
   the owner decisions and review named there before any cutover execution.
2. **Cutover reconciliation must equal zero** (standing deployment gate 3).
   Timeout is never green; the reconciliation query set and its zero-variance
   target must be named in the unlock.
3. **Named owner cutover unlock** (frozen `GATES.md` §“F2 slice-01”: “Cutover
   unlock (gen-1 synthetic shop) — **OPEN — separately locked**”). Owner actor,
   pre-checks, and acceptance-recorded evidence are required.

Production-scope gates that must **not** be conflated with a staging cutover,
and which remain open independently:

4. Human approval before any production schema application (standing gate 1).
5. Production membership unique index `(shop_id, clerk_user_id)` (standing gate 2).
6. `MIGRATOR-ROLE-PROVISIONING-GATE` — blocks production schema application and
   deployment.
7. Manual-resolution workflow for duplicate suspicions — required before
   production outbound cutover.
8. Adjust-slice completion — required before production inventory-truth cutover.
9. `CSV-COST-FEEDBACK-GATE` — blocks production use of CSV adjust.

Recorded but not slice blockers: the two **pre-existing non-F2** privilege
follow-ups in `GATES-POINTER-F2-SLICE-01.md` (runtime INSERT on identity
`shops`/`shop_members`; USAGE/SELECT/UPDATE on non-F2 truth sequences). A future
runtime least-privilege review should disposition them.

## What a cutover unlock must specify (owner decisions — not made here)

- The named **gen-1 synthetic shop** (shop identity plus its owner membership)
  and the Clerk actor used.
- The exact **cutover row / flag** content for `inventory_truth_cutover`, who
  inserts it, with which role or credential, and how it is reversed. The pooled
  runtime role currently has no table-wide UPDATE or DELETE on envelope objects,
  so the write path and its privilege requirement must be stated explicitly.
- The **idempotency-key convention** for the first controlled receive
  (`purchase_record.client_idempotency_key`, max 36 characters).
- The **pre- and post-cutover reconciliation** query set, the zero-variance
  requirement, and the baseline digest to compare against.
- **Audit logging** expectations and the **break-glass / rollback** path. Grant
  rollback restores SELECT-only while preserving the column, index, and evidence
  rows (contract §12 policy).
- The evidence to record in
  `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md` and in the successor
  checkpoint that closes this planning record.
- An explicit restatement of what stays **off**: worker, Shopify, notifications,
  Web Push, payments, Watch, production schema, production deploy, and
  production credentials.

## Terminal states for this planning record

| State | Meaning |
| --- | --- |
| `PREPARED — PLANNING ONLY` | current state; nothing approved or executed |
| `RUNBOOK READY FOR REVIEW` | a cutover runbook, audit-logging plan, and break-glass procedure exist and are named for review |
| `CUTOVER UNLOCKED` | a named owner unlock authorizes one staging gen-1 cutover with a zero-variance reconciliation target |
| `CUTOVER EXECUTED — RECONCILED ZERO` | the single authorized cutover ran and reconciled to zero; recorded in the acceptance record |
| `REJECTED — OWNER ACTION REQUIRED` | a precondition cannot be met; the named blocker and owner are recorded and work stops |

Timeout is never success. A rejected or timed-out attempt does not start another
planning loop; it names the failed precondition and the owner and stops.

## Explicitly not this checkpoint

- Approval or execution of cutover; creation of any `inventory_truth_cutover`
  row; enabling any feature flag.
- Any successful receive or other inventory write.
- Any redeploy, autodeploy enablement, seed, privilege or grant change, or use
  of a migrator credential.
- Any production contact, production schema apply, or production deploy.
- Any edit to frozen contract, design, migration, test, amendment, or
  `GATES.md` text.

## Next step

**Done as planned:** the cutover **runbook, audit-record, break-glass,
zero-reconciliation, and rollback/stop-condition** plan was prepared as a
separate planning-only documentation slice —
`CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md`. It reads the gate mechanism from
code rather than assuming it, and lists the seven owner decisions that must be
answered first.

**Remaining:** the owner records those decisions, the runbook is approved
verbatim, and only then is a named cutover unlock requested for one staging
gen-1 synthetic shop with a zero-variance reconciliation target. Until that
unlock is granted and executed, the receive endpoint stays deployed and
fail-closed.
