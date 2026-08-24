# Slice-03 planning reviews

**Subject:** `DIRECTIVE-SLICE-03.md` + proposed `amendments/AMENDMENT-1.2.0.md`
**Against:** frozen `STASHTAB-INVENTORY-TRUTH-001` v1.1.0
**Pinned commit:** `1a54722` (`feature/inventory-truth-slice-02`)
**Mode:** planning only; no implementation

Independent reviews below. Agreement is not acceptance. One bounded
correction pass was applied to the directive (lotless `adjust` instead of
live `loss`; CSV all-or-nothing; CSV cost containment). Final
verification follows.

## Architecture

**Verdict:** PASS with amendment required.

Cite: DESIGN.md §1 already lists `adjust` as QUANTITY_CHANGING but
receive-first “MUST NOT insert” other types; live inserts need 1.2.0.
DESIGN.md §3 requires `lot_id` for receive/loss. Using live `loss` for
shrinkage would force lot attachment and collide with owner decision 6
(no cost/lot mutation). Correction: live staff paths insert lotless
`adjust`; backfill `loss` stays lot-required.

FastAPI remains the only writer. Snapshot stays display. Partner vendor
`item.stock =` paths are not live SaaS.

**Exceeds v1.1.0 envelope:** yes — keys, evidence table, reason registry.

## Data-integrity

**Verdict:** PASS after correction.

Canonical keys follow `{source}:{shop_id}:{source_pk}`. Unique
(shop_id, key) plus CSV (shop, upload, row). Absolute targets converted
under row lock so two files cannot clobber without an event. qty_after =
qty_before + delta is a check constraint. Historical silent overwrites
are not backfilled (stated). Cost fields excluded from the writer; CSV
existing-row cost is contained.

Idempotent replay vs conflict is defined. Duplicate CSV identities are
defined (collapse equal, reject conflicting).

## Database-security

**Verdict:** PASS with same controls as slice-02.

New table is migrator-only, TruthBase, composite FKs RESTRICT,
append-only UPDATE/DELETE/TRUNCATE deny, runtime role cannot create it
via `create_all`. Migrator-role provisioning gate already blocks
production apply. No extra superuser behavior.

## Application-security / authorization

**Verdict:** PASS.

Cite: `deps.py` ShopContext from verified token + membership; headers are
hints. Roles in `shop.py` are `owner` | `staff`. CSV owner-only matches
existing invite/owner gates in `shops.py` / admin. Actor is
`ctx.clerk_user_id`, never a body field. Missing actor fails closed.

## Adversarial / concurrency

**Verdict:** PASS after correction.

Row lock + populate_existing (proven necessary in slice-02). Negative
remaining rejects the transaction. Shopify oversale remains on sell
path; adjust cannot use it to go negative. CSV all-or-nothing removes
partial-file races. Same UUID different payload is conflict, not a
second delta. Corrected CSV must use a new upload UUID so operators
cannot “edit” history.

## Operations / rollback

**Verdict:** PASS.

Freeze keeps quantity PATCH/CSV at 503. Rollback = cutover flip;
snapshot/Sale unchanged; adjustment rows remain evidence. Alert
delivery is non-blocking. Threshold numbers are defaults pending owner
confirm (residual decision, not a blocker for plan freeze after
amendment).

## Workflow-liveness

**Verdict:** PASS.

No new human-resolution queue is required to keep inventory moving:
rejected adjusts fail closed and the client retries. Anomaly exceptions
are alerts, not blockers. Cycle-count campaign UI is explicitly out of
scope so this slice cannot stall on an unscoped product. CSV all-or-
nothing can stall a large import on one bad row — that is intended fail-
closed, not a deadlock; the operator fixes the file.

## Bounded correction pass (applied to the directive)

1. Live shrinkage/damage/theft → `adjust` + loss-class reason, not
   `event_type=loss`.
2. CSV atomicity chosen: validate all, then one transaction.
3. CSV existing-row cost writes contained (skip).
4. New CSV items classified as qty-before 0 adjust.
5. Amendment 1.2.0 drafted instead of editing frozen bodies.

## Final verification

- Owner decisions 1–7 are reflected in the directive without silent
  widening of cycle-count UI or cost correction.
- Mutation-path inventory covers every live `services/api/app` stock
  writer found by search.
- v1.1.0 cannot absorb keys/evidence table → amendment required.
- Frozen DESIGN/MIGRATION/TESTS/CONTRACT bodies were not modified.
- No code, tests, migrations, commits, or production credentials used
  in this planning pass.

**Overall:** plan is ready for the Amendment 1.2.0 vote, then freeze of
the slice-03 plan against v1.2.0. Implementation remains blocked.
