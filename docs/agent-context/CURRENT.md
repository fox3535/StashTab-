# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-09-04
**Branch:** `main` at `0a244a5` (PR #34 merged as a merge commit; parents
`ec9f72c` and `4589b64`); planning-only cutover operations plan on
`docs/f2-cutover-operations-plan` (draft PR pending); no other PR open —
`feature/f1-vendor-core-recovery-batch` is pushed on `origin` at `19efd9a` with
no open PR
**Staging API:** Railway deploy `44317623` of `main` at `ec9f72c` — verified
fail-closed 2026-09-04 (D-043); unchanged by the PR #34 merge (D-044);
supersedes `9c47945a` (D-039 staging smoke)

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.1 and 1.1.2 frozen.
  Web Push off. Local 1.1.2 backend on `main` as `c3647a4`; not in production.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.3.0** — frozen (AMENDMENT-1.3.0 on `main`
  via `9870468`). Slices 01–03 on `main` via `c3647a4`. F2 controlled receive
  **merged on `main` via PR #31** (`a354fed`). F2 staging provisioning
  **applied on `stashtab_staging` and reconciled/verified 2026-09-04** (D-042):
  column/index/grants only, business tables empty, cutover OFF. F2 code
  **deployed to the staging API and verified fail-closed 2026-09-04** (D-043).
  Staging schema for slices 01–03 applied 2026-08-27 (D-028). Not production.

## Current phase

`frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`
**Status:** `ACCEPTED — MERGED ON main — STAGING SMOKE PASSED — FRONTEND NOT DEPLOYED` (D-038, D-039).
F0 exit remains passed for frontend recovery (D-035). Memberships read is
hosted on staging via deploy `44317623`. Frontend was smoke-tested locally
at `http://localhost:3001`, never deployed; that local dev server was started
only to enable the owner's F2 probe and has been stopped.

Writes, worker, Shopify, notifications, Watch remain off. Convex is out (D-024).

## Approved boundaries

- Python/FastAPI owns business logic; tenant data uses `shop_id`.
- Identity: signed token + membership. Shop header is an untrusted hint.
- Partner Python is `vendor/mimir-partner/`; inspect, do not copy blindly.
- Humans approve writes, Web Push, payments, Watch, and later slices.

## Active gates

1. Identity smoke: **closed** (D-025).
2. Inventory schema on staging: **closed** (D-028).
3. Inventory read smoke: **closed** (D-029). Writes still off.
4. Production schema apply blocked.
5. Card-resolution intake/abstention: **merged, feature off** (D-034 / PR #13).
6. F0 exit for frontend recovery: **passed** (D-035).
7. My-shop memberships read: **merged on `main` via PR #15** (D-037), hosted on staging via deploy `44317623`.
8. F1 slice-01 shell + read inventory: **accepted** (D-038 local, D-039 live smoke).
   Merged on `main` `3c3ca33`; staging smoke passed: real Clerk memberships,
   live staging inventory read, full keyboard walkthrough, mobile, sign-out
   and re-sign-in. No schema or data writes.
9. F2 slice-01 controlled receive: **merged on `main`** (D-040 local, D-041 merge).
   PR #31 merge `a354fed`. **Staging provisioning applied and verified
   2026-09-04** (D-042). **API-only staging deployment executed once and
   verified fail-closed 2026-09-04** (D-043; deploy `44317623` of `main` at
   `ec9f72c`, autodeploy off, no worker): health and ready `200`, all flags
   `false`, unauthenticated receive `401`, exactly one authenticated probe `503`
   `FEATURE_NOT_READY` after membership resolution and before any write, Neon
   row counts unchanged, both probe markers absent, grants/column/index
   unchanged. Endpoint **deployed but fail-closed**; provisioning **complete**;
   cutover OFF and endpoint use stays locked until a separate cutover unlock.
   Evidence: `CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`,
   `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`,
   `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`,
   `GATES-POINTER-F2-SLICE-01.md`. Verification record **merged to `main` as
   `0a244a5`** (D-044); the merge caused no deployment, migration, cutover,
   receive call, privilege change, or cloud write.

## Next queued phases

1. F2 staging provisioning, the API-only staging deployment, and the merged
   verification record are **done** and fail-closed. The cutover **runbook,
   audit record, break-glass procedure, zero-reconciliation gate (R1–R7), and
   stop/rollback conditions (S1–S11)** are now drafted **planning only** in
   `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md`, which names seven required owner
   decisions and approves nothing. Next: the owner records those decisions, then
   the runbook is approved verbatim, then a **separate** named cutover unlock.
   `CHECKPOINT-F2-CUTOVER-PLANNING.md` is planning only too. Do not use the
   receive endpoint until cutover is unlocked. F1 vendor-core batch remains
   unmerged with no open PR (`F1-VENDOR-CORE-BATCH-PRESERVATION.md`).
2. Frontend recovery continuation: next slice planning per
   `docs/frontend-recovery-v1/`; navigation/deferred-routes cleanup item for
   bare `/admin/shopify` 404 (non-blocking UX backlog).
3. Later enablement, not F0: inventory write staging smoke, notification
   staging apply, production restore drill.
4. Do not enable card-resolution, writes, or push without a named unlock.
