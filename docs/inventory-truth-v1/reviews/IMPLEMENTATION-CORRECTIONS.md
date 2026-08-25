# Post-review corrections — slice-01-receive-foundation

**Date:** 2026-08-23  
**Reviews run:** Architecture, Data-integrity, Database-security,
Adversarial/concurrency, Operations/rollback (independent).  
**Rule applied:** only clear slice-local defects corrected; one bounded
verification pass afterwards; no open review loop.

## Corrections applied

1. **Freeze now enforced on live receive paths (P0, three reviewers).**
   `_truth_dual_write_staging_commit` and
   `_truth_dual_write_purchase_receive` call `require_receive_open`:
   staging commit and trade receive are rejected while the shop has no
   completed cutover. The silent "skip truth write" behavior is removed.
   Negative tests: frozen shop rejects with `ReceiveFrozenError`, no
   snapshot mutation, no truth rows.
2. **Savepoint correctness in `_write_pair` (P1).** One nested transaction
   wraps existence checks + inserts; a concurrent-duplicate unique
   violation rolls back only that savepoint, so the caller's already-
   flushed snapshot updates survive. Non-uniqueness integrity failures
   (e.g. FK restrict) surface as `PermanentPairError` instead of being
   masked as benign retries.
3. **Rebuilt event derived from stored lot (P1).** If a lot exists without
   its event, type/delta come from the stored lot's source/quantity; the
   no-op check also verifies event type, not just quantity. Mismatched
   retries raise rather than corrupting the pair invariant.
4. **CSV stock overwrite frozen (P0/P1).** `/admin/import` calls the
   freeze guard; MIGRATION.md order step 3 lists CSV overwrite as must-
   freeze.
5. **PATCH stock stays frozen after cutover (P1).** Direct stock
   overwrites unlock only with the later adjust slice (order step 5), not
   when cutover completes. Guard rejects with 503 regardless of status.
6. **Cutover row locks (P0 per adversarial review).** `run_cutover`
   selects the shop's `inventory_item` and `purchase_record` rows
   `FOR UPDATE` inside the cutover transaction before computing gaps, per
   order step 4, closing the mid-cutover receive race on Postgres.
7. **Migrator creates truth tables only (P2).** The create list is pinned
   to `TRUTH_TABLE_NAMES`; shadow parent definitions can never be emitted.
   Post-apply verification asserts tables + required indexes exist or
   raises loudly.
8. **Migrator-only import letter restored (P2).** `admin.py` no longer
   imports `truth_core` at module load; all three `/inventory-truth/*`
   endpoints lazy-import it. `models_truth` docstring corrected: import
   runs no DDL; application metadata never contains these tables.
9. **Cutover endpoint governance (P2).** Owner role required;
   request generation pinned server-side to 1 (`ge=1, le=1`) so gen:2+
   cannot be minted via API without an authorized amendment.

## Bounded verification pass

`pytest tests/` → **90 passed** (70 prior identity/logic/notification +
20 slice tests including new freeze negatives and rollback-flip drill).

Verified explicitly after corrections:

- Frozen shop: staging commit rejected cleanly (500-free), snapshot and
  truth tables untouched.
- Completed-cutover shop: receive dual-writes pair; recon zero; PATCH/
  CSV stock overwrite still 503.
- Operator rollback drill: flipping cutover row to `locking` refreezes
  receives with no deploy and no snapshot damage; re-running cutover
  restores completion; recon stays zero.
- Migrator idempotency and verification assertions hold on re-run.

## Residual items (not corrected here)

- `run_cutover` commits internally and remains callable by an owner via
  API; production schema apply stays human-gated per contract. Ops
  runbook + audit-log entry for cutover invocations are follow-ups
  (DATABASE-CONTROLS §7 alignment).
- SQLite ignores `FOR UPDATE`; locking semantics verified by design
  reading, not by a Postgres CI leg. Follow-up: add Postgres test leg
  before any shared deployment. **Resolved 2026-08-23:** the PostgreSQL
  acceptance harness now runs on real Postgres (disposable container) and
  as a blocking CI job — see `SLICE-01-PG-ACCEPTANCE.md`.
- No kill-switch env var for dual-write; documented rollback lever is the
  cutover row flip (deploy-free). Break-glass path (code deploy) noted in
  implementation record.
