# DIRECTIVE (PROPOSED — NOT IMPLEMENTED) — slice-02-outbound-events

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.0.0 (frozen)
**Version:** 3 (post-review correction pass; supersedes v2)
**Prepared:** 2026-08-23; revised same day after independent reviews
(Architecture, Data-integrity, Database-security,
Adversarial/concurrency, Workflow-liveness) and ONE bounded correction
pass.
**Status:** `PLAN READY FOR FREEZE DECISION — NO IMPLEMENTATION AUTHORIZED`
**Predecessor:** `slice-01-receive-foundation` (`COMPLETED — NOT DEPLOYED`,
`ACCEPTANCE-SLICE-01.md`)

Owner-approved planning decisions baked in:

1. Financial refund ≠ restock. Inventory increases only on vendor-confirmed
   physical return of whole resalable units.
2. Partial monetary refunds are independent of inventory; only confirmed
   whole-unit returns create positive quantity.
3. Refund/return records are append-only and reference the original
   sale/outbound event; original history is never deleted or rewritten.
   Financial-refund execution stays out of this inventory slice.
4. POS rejects insufficient-stock sales outright. External Shopify
   over-sale: keep the external sale record, write the event for quantity
   actually removed, raise a critical exception preserving the shortage,
   alert the vendor, keep auto-pause, never silently clamp or fabricate
   full sells.
5. Outbound ships before adjustments. Admin PATCH / CSV absolute overwrites
   stay frozen. The adjustment slice must be completed before any
   production inventory-truth cutover.

## 0. What changed from v2 (correction-pass summary)

Independent reviews converged on one fatal defect plus supporting gaps:

- **v2's registry could never arbitrate POS-vs-pull races**: each channel
  minted its own disjoint `txn_ref`, so the unique constraint never fired
  across channels and double decrements survived unchanged (Architecture
  F1 P0, Adversarial F1 P0, Data-integrity P0-2).
- v2's per-order registry uniqueness dropped sibling lines of multi-line
  orders (Data-integrity P0-1).
- v2's `:short` key class was chosen from live stock, enabling double-count
  after stock recovered (Data-integrity P0-3); it also violates the frozen
  key grammar (Architecture F3).
- Merchant-declared linkage could silently swallow a genuine sale
  (Adversarial F2 P0).

v3 replaces correlation-string arbitration with a **per-line observation
ledger** that arbitrates on durable channel identities only, treats any
cross-channel duplicate claim as fail-closed, and removes all silent-merge
paths.

## 1. Complete outbound-path inventory (verified against current code)

| # | Path | Where | Today's quantity effect | Sale row? | In-slice |
|---|---|---|---|---|---|
| O1 | POS checkout | `app/logic/sales.py` `finalize_sale`; route `app/routers/sales.py::checkout` | `item.stock -= qty` per line; SyncOutbox `stock_update` | Yes (per line) | **Yes** |
| O2 | Trade settlement | `app/logic/trades.py` — receive is inbound (slice-01); resale exits via POS | none directly | via POS | No direct decrement |
| O3 | Show sales | POS with `show_session_id` (same `finalize_sale`) | same as O1 | Yes | Covered by O1 |
| O4 | Shopify order pull | `app/logic/sync_worker.py::pull_shopify_orders` (~145) | clamped decrement at 0; auto-pause at 0; OnlinePullQueue row | Yes (`online`) | **Yes** |
| O5 | Cancellations/refunds | No code exists today; Collectr recon produces manual removal list | n/a | n/a | Design-only (§5) |
| O6 | Admin PATCH inventory | `app/routers/admin.py` absolute `stock=` | overwrite (frozen 503) | No | Blocked until adjust slice |
| O7 | CSV import overwrite | `app/logic/import_engine.py` absolute `stock=` | overwrite (frozen) | No | Blocked until adjust slice |
| O8 | Collectr removals | `app/logic/reconciliation.py` report-only | none today | No | Out of scope |
| O9 | Other direct stock mutation | Grep shows only sites above | — | — | Gate test re-runs grep |

Shopify remains owner of online order state; SyncOutbox push direction is
untouched.

## 2. Proposed slice boundaries

In scope:

1. Outbound dual-write for POS/show lines (O1/O3): one `sell` event per
   line in the same transaction as its Sale row.
2. Outbound dual-write for online-pull lines (O4) with per-line observation
   arbitration (§3) and over-sale exception handling (§6).
3. Insufficient-stock rejection for POS (decision 4).
4. Freeze semantics identical to slice-01, fail-closed.
5. Reconciliation extension incl. typed exception register.
6. Refund/return model + append-only table designs + tests only (no
   financial execution).

Out of scope: financial refund flows; PATCH/CSV unlock (adjust slice;
must precede production cutover per decision 5); overlay writes; COGS
changes; Shopify push changes; new UI.

Preserved invariants (test-asserted): identical Sale rows for accepted
sales; weighted-average cost never touched by outbound paths; POS shapes
unchanged except explicit insufficient-stock rejection; Shopify owns
online orders.

## 3. Cross-channel duplicate handling (corrected design)

### Why v2 failed

POS and pull minted different correlation strings (`pos:{shop}:{receipt}`
vs `shopify:{shop}:{order}`), which never collide — so "arbitration by
unique constraint" was inert exactly where it mattered, and every proposed
match basis beyond platform identity was either out of scope this slice or
a silent-merge hazard.

### v3 mechanism: per-line observation ledger, fail-closed

New migrator-created, shop-scoped table `inventory_channel_observation`
(the only cross-channel structure):

```
id, shop_id, channel ('pos'|'shopify'), channel_ref (durable native id),
sale_id (nullable), created_at
UNIQUE (shop_id, channel, channel_ref)
```

- `channel='pos', channel_ref={sale.id}` — inserted in the same transaction
  as the POS truth pair.
- `channel='shopify', channel_ref={order_id}:{line_id}` — inserted in the
  same transaction as the pull truth pair.
- Uniqueness gives intra-channel retry safety (replaces reliance on the
  worker's non-transactional existence check, which two overlapping
  schedulers can race — Adversarial F4).

**Cross-channel detection is deliberately NOT automatic.** There is no
reliable bridge between a counter receipt and an online order in the
current product: no POS-created-Shopify-order flow exists, and SKU+amount+
time matching is prohibited (identical twins are routine). Therefore:

1. If both observations exist for what the vendor later establishes is one
   transaction, reconciliation surfaces it as a **duplicate-suspicion
   exception** (see below) — never auto-merged.
2. The only accepted pre-count link is a future explicit integration where
   one system creates/annotates the other's order carrying the counterpart
   identity; until such an integration ships (out of scope), cross-channel
   duplicates are handled by detection + exception + human resolution, not
   prevention at write time.

### Duplicate-suspicion exception

Reconciliation compares, per shop: total POS-observed units vs total
pull-observed units vs event-derived movement, per SKU within a bounded
window. When POS units + pull units exceed true available evidence
(snapshot delta + received stock), a critical `duplicate_suspicion`
exception row names both candidate observations. Resolution (confirm
double-count → compensating `reverse` event referencing both; confirm two
real sales → dismiss) is a follow-up resolution flow with owner-gated
access; this slice creates and surfaces exceptions only.

This satisfies the owner requirement: behaviour when reliable correlation
is unavailable is to raise an exception rather than guess — extended to
"never merge on similarity at any layer."

### Legacy rows without identifiers

- Existing Sales/events predate observations; they get no backfilled
  ledger rows and are never auto-linked.
- At this slice's cutover: freeze → drain outstanding pull queue under
  legacy rules → run gap reconciliation → lift freeze with dual-write, so
  live traffic always starts with clean observation state.
- Pre-cutover decrements are already captured by slice-01's opening-gap
  backfill; no retroactive linking occurs.

### Races between POS finalize and pull (serialization)

Both writers insert into the observation ledger inside their truth-pair
transaction; PostgreSQL unique constraints serialize contention:

- Same channel+ref re-insert (worker retry, scheduler overlap) → unique
  violation → treated as already-processed → no-op (no second decrement,
  no second event). This closes the OnlinePullQueue check-then-insert race
  (Adversarial F4) because arbitration is now transactional.
- Cross-channel "same sale" has no shared identity to contend on by design
  → both proceed → later detected by §3 duplicate-suspicion reconciliation
  → exception + human resolution. Never a silent merge, never a guessed
  no-op.

The loser of a same-channel race performs NO snapshot decrement (its whole
transaction rolls back to the savepoint before any stock write), keeping
the frozen quantity equation intact (resolves Data-integrity P0-2: loser
skips decrement AND writes nothing; "legacy behaviour unchanged" applies
only to genuinely distinct sales).

## 4. Canonical outbound idempotency sources

Frozen grammar `{source}:{shop_id}:{source_pk}` with the locked single
`:gen:{n}` suffix rule — **no `:short` suffix exists in v3** (removes the
grammar violation; Architecture F3, Data-integrity P0-3):

| Source | Idempotency key |
|---|---|
| POS/show line | `sell_sale:{shop_id}:{sale.id}` |
| Pull line (full) | `sell_shopify_order_line:{shop_id}:{order_id}:{line_id}` |
| Pull line short-sale | SAME key as full (`sell_shopify_order_line:…`) |

Short-sale handling without a suffix: the event's stored fields carry the
truth (delta = −S actually removed; `reason` = `short:{Q-S}` marker ≤60
chars). Key class therefore derives from nothing mutable — retries hit the
identical key regardless of current stock, and the existing five-step
mismatch rule catches contradictory retries as `failed_permanent` instead
of writing a second event (resolves Data-integrity P0-3; poison-batch
contained by §6 step 7).

Lotless-outbound collision rules (Architecture F4): the outbound
counterpart pair is **event ↔ observation-ledger row ↔ Sale row**, not
lot↔event. Rules: both exist with consistent type/delta → no-op; event w/o
observation row → rebuild row; observation w/o event → rebuild event from
stored observation/Sale data; contradiction → `failed_permanent`. Event
without Sale (POS path) → `failed_permanent`. These mirror DESIGN §2
step-for-step and need tests 2–3 equivalents.

Contract amendment required before freeze: DESIGN.md §2 canonical-key
examples gain the two outbound sources above (values only, grammar
unchanged); MIGRATION.md envelope gains the four additive structures +
`txn_ref`-free event columns (`sale_id` now populated for sell events,
`reason` markers documented). Per CONTRACT §6 this is a versioned
amendment packet — a named human decision blocker (§10 Q1).

## 5. Refund / return model (append-only; inventory only on confirmed units)

Proposed migrator-created tables (all extend `TruthBase` and
`TRUTH_TABLE_NAMES` so startup `create_all` can never create them —
Database-security F1):

- `refund_record` (append-only): `shop_id`, references the originating
  **outbound InventoryEvent** `(shop_id, id)` via composite FK ON DELETE
  RESTRICT (deterministic single target — Architecture F7), amount, reason,
  actor, created_at. No UPDATE/DELETE path at application level.
- `return_record` (append-only): references `refund_record`
  `(shop_id, id)` composite FK, whole-unit count, condition note, confirming
  vendor actor, created_at.
- Confirmed return → exactly one positive `receive`-class event keyed
  `{return_record_source}:{shop_id}:{return_record.id}`, written in the
  SAME transaction as the `return_record` insert (pair pattern from
  `_write_pair`; crash cannot strand a confirmed return without inventory —
  Data-integrity P2-2). Repeat confirm hits the same key → no-op.
- Original sale/outbound rows are never updated or deleted; corrections use
  reserved `reverse` + `reverses_event_id`.
- Sell events populate `sale_id` (composite FK already shipped in slice-01
  schema) so lineage is provable without overloading the 60-char `reason`
  (Data-integrity P2-3).
- Append-only enforcement: DB-level control required — REVOKE UPDATE/
  DELETE on these tables for the application role, or BEFORE-trigger raise,
  chosen at implementation time; PG acceptance test attempts UPDATE/DELETE
  and expects failure (Database-security F3; audit logging per
  DATABASE-CONTROLS §7 recorded as standing gate).
- Late merchant linkage: if both sides were already counted, the resolution
  flow may only emit a compensating `reverse` event; it can never delete or
  rewrite pairs (closes Data-integrity P1-1).

## 6. Over-sale exception model (external Shopify oversell)

For a pulled line requesting Q with snapshot S < Q:

1. Preserve external sale record + OnlinePullQueue row (Shopify owns the
   fact a sale happened).
2. Decrement snapshot by S (display floors at zero, unchanged behaviour)
   and write ONE `sell` event, key `sell_shopify_order_line:…`, delta −S,
   reason marker `short:{Q−S}`.
3. Insert critical `inventory_exception` row (shop-scoped, TruthBase):
   kind `over_sale_short`, unsatisfied qty Q−S, requested vs removed,
   channel refs, status `open` — same transaction as step 2 (atomic;
   Adversarial F3c).
4. Vendor alert via existing notification pathway (critical); auto-pause at
   zero untouched.
5. Retries/re-polls hit the same key: first writer wins, later ones no-op —
   regardless of intervening stock changes, because the key does not encode
   S (Data-integrity P0-3 closed). A retry whose computed delta contradicts
   the stored event raises `failed_permanent` for that line only; the pull
   loop catches per-line `failed_permanent`, records it, and CONTINUES with
   other orders instead of aborting the batch (poison-order containment —
   Adversarial F3b).
6. Exception arithmetic: reconcile uses removed-quantity events, so
   event-derived remaining equals the zero-floored snapshot exactly; the
   shortage lives in the register, never as phantom inventory.
7. Open critical exceptions do NOT block further selling of other SKUs;
   whether repeated oversells of the same SKU stack exceptions is recorded
   as decision Q5 (they stack by default).
8. Exception read access requires verified shop membership (identity
   slice); resolution endpoints (follow-up flow) require an explicit
   authorized role + audit entry (Database-security F7).

## 7. Reconciliation requirements

- Equation stays `SUM(quantity_delta)` per shop+SKU including `sell`
  negatives and confirmed-return positives; snapshot authoritative display
  during dual-write.
- Reconcile output adds: open exception list (shortages, duplicate
  suspicions) and per-channel observation totals so a suspected
  cross-channel duplicate is visible with both candidate refs.
- Production cutover gates: zero mismatches AND zero open critical
  exceptions AND adjust slice completed (decision 5 ordering recorded in
  GATES.md — Workflow-liveness P1-2). Timeout is never success.

## 8. Acceptance tests (proposed)

1. POS line → event + observation row + populated `sale_id`; Sale rows
   identical to pre-slice.
2. POS retry (same sale) → no-op via key; observation unique violation →
   no second decrement.
3. Pull retry / overlapping schedulers same order → exactly one
   decrement set; ledger arbitration transactional (closes the
   check-then-insert race).
4. **Cross-channel same-real-sale** (both observe simultaneously):
   both events legitimately exist; test asserts NO merge occurred, both
   observations recorded, duplicate_suspicion exception raised at next
   reconcile, and SUM(delta) reflects the raw sum until a human resolves —
   i.e., fail-visible, not fail-silent (rewritten from unpassable v2 test;
   Architecture F1, Adversarial F5).
5. Two genuinely distinct same-SKU/same-price sales minutes apart → both
   counted; no exception (no second observation claims them).
6. Over-sell pull Q>S → −S event with short marker + open exception Q−S;
   external sale preserved; second pull no-op even if stock was since
   replenished (key stability); auto-pause fired; notification emitted;
   batch continues past a poisoned line.
7. Contradictory retry (different computed delta, same key) →
   `failed_permanent` for that line, batch continues, no second event.
8. Insufficient-stock POS cart → rejected before any write.
9. Refund without return → `refund_record` only; inventory unchanged;
   UPDATE/DELETE attempt on refund/return rows fails at DB level (negative
   test).
10. Confirmed return → single positive event in same transaction; repeat
    confirm no-op; originals untouched.
11. Freeze: outbound rejects while frozen (503) incl. show mode; rollback
    drill flips cutover row; snapshot/Sale/WA unchanged; freeze backlog
    drains under legacy rules then reconciles before dual-write resumes
    (freeze-burst drain ordering asserted).
12. PG harness extension in blocking CI job: same-channel race, scheduler-
    overlap race, over-sale retry-after-restock; grep-gate proves no
    un-inventoried stock mutation outside the O-list; create_all-prevention
    test proves the four new tables are absent from application metadata.

## 9. Rollback approach

Flip cutover status to `locking`: outbound dual-writes stop. Frozen-window
pulls accrue in Shopify (existing behaviour) and are drained under LEGACY
rules at refreeze — with an explicit post-drain reconciliation checkpoint
before dual-write resumes, so the burst cannot silently manufacture
over-sales (Adversarial F4). Observation/exception/refund/return tables and
truth tables may be dropped without touching `Sale`, `InventoryItem`,
`PurchaseRecord`, `OnlinePullQueue`, or SyncOutbox. (v2's incorrect
"resume legacy-only decrements while frozen" wording removed.)

## 10. Remaining genuine human decisions

1. **Amendment vote (blocking)**: approve the CONTRACT §6 amendment packet
   adding the two outbound canonical keys and the migration-envelope
   additions (required before implementation unlock; `:short` question
   resolved by removal).
2. Q2 — Manual linkage/resolution UX timing (resolution flow is follow-up;
   slice-02 stores and surfaces exceptions only).
3. Q3 — Notification routing/severity for over-sale alerts.
4. Q5 — Confirm repeated oversells stack exceptions (default: yes).
5. Q6 — POS insufficient-stock HTTP status (409 recommended).
6. Q7 — "Resalable" condition definition owner.
7. Q8 — Registry justification: keep observation ledger (recommended — it
   also fixes the scheduler-overlap race) vs rely on a unique index on
   OnlinePullQueue alone (smaller, but leaves POS-side arbitration and
   duplicate-suspicion detection undefined).

## 11. Freeze recommendation

Recommend **READY FOR FREEZE DECISION**, conditional solely on the §10 Q1
contract-amendment vote. The corrected design removes every silent-merge
path (fail-closed everywhere), keeps all legacy invariants test-enforced,
sequences adjustment before production cutover, and confines open
questions to bounded, named decisions that do not alter slice boundaries.
