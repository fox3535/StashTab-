# REVIEW — R1 SQL against frozen inventory-truth 1.3.0

**Reviewer role:** independent data-integrity / contract review, separate from
the authoring pass.
**Subject:** the R1 invariant as implemented in
`scripts/f2-cutover/sql/05-r1-r7.sql` (blocks R1a, R1c, R1d, R1b, R1e) and its
re-evaluation as F4 in `scripts/f2-cutover/sql/07-final-verification.sql`.
**Required by:** `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §5 — "R1's exact SQL
must be written against the frozen DESIGN/MIGRATION semantics by the implementer
of the cutover slice and independently reviewed."
**Pinned to:** branch `docs/f2-cutover-execution-packet` from protected `main` at
`aafae79`.
**Verdict:** `PASS WITH ONE RECORDED CONTRACT GAP` — the R1 SQL is faithful to
frozen 1.3.0. The gap is in the **accepted implementation's** CHECK constraint,
not in the R1 SQL; R1c arm (c) closes it at the gate, and the underlying schema
divergence is recorded below as finding **R1-1** for an owner decision.

No frozen file was edited to reach this verdict. No application code was
changed.

## 1. Authorities read, with exact locations

| # | Authority | Location | Text relied on |
| --- | --- | --- | --- |
| A1 | Frozen `DESIGN.md` §1 | L17–L22 | `QUANTITY_CHANGING = receive \| sell \| loss \| return \| damage \| adjust \| reverse (only if the reversed event is QUANTITY_CHANGING)`; `OVERLAY = reserve \| release \| move \| channel_commit \| quarantine \| reverse (only if the reversed event is OVERLAY)` |
| A2 | Frozen `DESIGN.md` §1 | L29–L31 | "**Overlay events MUST set `quantity_delta = 0`.** They MAY set `overlay_quantity` (int) … They **never** enter remaining or recon." |
| A3 | Frozen `DESIGN.md` §1 | L45–L54 | **Locked recon (SKU), receive-first slice:** `event_remaining(shop_id, sku) = SUM(quantity_delta) FROM inventory_event WHERE shop_id = :shop_id AND sku = :sku`; `unaccounted if event_remaining != inventory_item.stock` |
| A4 | Frozen `DESIGN.md` §1 | L56–L58 | "`quantity_acquired` on the lot header is denormalized evidence and **MUST equal** the lot's `receive.quantity_delta`. It is **never** added to the sum." |
| A5 | Frozen `MIGRATION.md` | L143–L148 | **Reconciliation:** `event_remaining(sku) = SUM(quantity_delta) for shop+sku`; `unaccounted if event_remaining != inventory_item.stock` |
| A6 | Frozen `MIGRATION.md` | L120–L122 | `gap = inventory_item.stock - SUM(quantity_delta for that shop+sku)` — fixes the sign convention: snapshot minus truth |
| A7 | Frozen `MIGRATION.md` | L51–L53 | "Insert `inventory_truth_cutover (shop_id, generation=1, status=locking, frozen_at=now())` or fail if a completed gen:1 exists." |
| A8 | `AMENDMENT-1.3.0` | §5 | F2 receive envelope: `purchase_record.client_idempotency_key VARCHAR(36)`, partial unique index, `Idempotency-Key` header must be a UUIDv4 of 36 characters |
| A9 | Accepted implementation | `services/api/app/inventory_truth/core.py` L419–L445 | `reconcile_shop()` — the accepted implementation of A3/A5 |
| A10 | Accepted implementation | `services/api/app/inventory_truth/core.py` L326–L329 | `func_event_delta_sum()` returns `func.coalesce(func.sum(InventoryEvent.quantity_delta), 0)` |
| A11 | Accepted model | `services/api/app/inventory_truth/models_truth.py` L71–L106 | `InventoryEvent`: `ck_event_type` (L77–L81), `ck_overlay_zero_delta` (L82–L86), `reverses_event_id` (L97), `quantity_delta` (L99), `overlay_quantity` (L100) |
| A12 | Accepted model | `services/api/app/models/inventory.py` L9–L36 | `InventoryItem`: `UniqueConstraint("shop_id", "sku", name="uq_inventory_shop_sku")` (L11), `sku` (L14), `stock` (L24) |
| A13 | Accepted migrator DDL | `services/api/app/inventory_live_schema/migrator.py` L74–L105 | `_CREATE_INVENTORY_ITEM`, with `CONSTRAINT uq_inventory_shop_sku UNIQUE (shop_id, sku)` at L103 |
| A14 | Plan §5 | `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` L203 | R1 zero condition: "`sum(inventory_item.stock)` for the shop equals the quantity derived from truth events for the same shop; variance exactly `0`" |

Precedence applied: frozen contract and amendments (A1–A8) first, then recorded
decisions, then the plan (A14). Where A14's prose and A3's locked wording could
be read differently, A3 governs and A14 is satisfied by it — see §3.6.

## 2. The SQL under review

R1b, the verdict (`05-r1-r7.sql`):

```sql
WITH event_remaining AS (
  SELECT sku, COALESCE(SUM(quantity_delta), 0)::bigint AS event_remaining
  FROM inventory_event
  WHERE shop_id = :'cutover_shop_id'
  GROUP BY sku
),
snapshot AS (
  SELECT sku, COALESCE(stock, 0)::bigint AS snapshot_stock
  FROM inventory_item
  WHERE shop_id = :'cutover_shop_id'
),
joined AS (
  SELECT COALESCE(snapshot.sku, event_remaining.sku) AS sku,
         COALESCE(event_remaining.event_remaining, 0) AS event_total,
         snapshot.snapshot_stock
  FROM snapshot
  FULL OUTER JOIN event_remaining ON event_remaining.sku = snapshot.sku
)
SELECT CASE
         WHEN (SELECT count(*) FROM joined
                WHERE snapshot_stock IS NULL
                   OR event_total <> snapshot_stock) = 0
          AND (SELECT COALESCE(SUM(event_total), 0) FROM joined)
              = (SELECT COALESCE(SUM(snapshot_stock), 0) FROM joined)
         THEN 'R1-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r1_snapshot_and_truth_variance')
       END AS r1_result;
```

F4 in `07-final-verification.sql` is the same query re-evaluated at the
`complete` point, with the marker `f2_verify_f4_r1_variance_at_complete`.
Identity of the two texts was verified by reading both, not assumed.

## 3. Clause-by-clause findings

### 3.1 The sum matches the locked wording exactly — PASS

A3 fixes `event_remaining(shop_id, sku) = SUM(quantity_delta) FROM
inventory_event WHERE shop_id = :shop_id AND sku = :sku`. The SQL groups by `sku`
under `WHERE shop_id = :'cutover_shop_id'`, which is the same partition expressed
once instead of per-SKU. `COALESCE(SUM(...), 0)` reproduces A10's
`func.coalesce(func.sum(...), 0)` byte-for-byte in semantics. `::bigint` widens
the `INTEGER` column so a large ledger cannot overflow the aggregate; widening
cannot change an equality that holds on the narrower type.

### 3.2 No `event_type` filter — PASS, and required

A3 and A5 both say `SUM(quantity_delta)` with no type predicate. Filtering to
`QUANTITY_CHANGING` would be a deviation, because A2 makes the filter
unnecessary: overlay deltas are 0 by contract, so they contribute nothing.
Adding a filter would also create a way for a mis-typed event to escape recon.
The SQL applies no filter. Correct.

### 3.3 `acquisition_lot.quantity_acquired` is excluded from the sum — PASS

A4: "**never** added to the sum." The R1b query does not reference
`acquisition_lot` at all. R1a deliberately selects it into a column named
`not_in_r1` so that an operator comparing the two outputs can see the value and
see that it is not part of the variance. Naming the column after its role,
rather than after its source, is intentional: a column called
`lot_quantity_acquired` in a reconciliation output invites someone to add it.

### 3.4 The mismatch condition reproduces `reconcile_shop()` — PASS

A9 walks `InventoryItem` rows for the shop, pops each SKU from the event map with
a default of `0`, records a mismatch when `remaining != int(item.stock or 0)`,
and then records a mismatch for every SKU **left over** in the event map with
`snapshot_stock: None`. The SQL reproduces all three behaviours:

| `reconcile_shop()` | R1b |
| --- | --- |
| `event_remaining.pop(item.sku, 0)` — missing event total is `0` | `COALESCE(event_remaining.event_remaining, 0) AS event_total` |
| `int(item.stock or 0)` — NULL stock is `0` | `COALESCE(stock, 0)::bigint AS snapshot_stock` |
| mismatch when `remaining != stock` | `event_total <> snapshot_stock` |
| leftover event SKU → `snapshot_stock: None` | `FULL OUTER JOIN` plus `snapshot_stock IS NULL` |

The `FULL OUTER JOIN` is load-bearing. An `INNER JOIN` would silently drop an
event SKU with no snapshot row — exactly the case `reconcile_shop()` reports as a
mismatch. A `LEFT JOIN` from `snapshot` would drop it too. Only the full outer
join makes the two readings equivalent, and only with the explicit
`snapshot_stock IS NULL` arm, because `NULL <> 0` is `NULL`, not `TRUE`, and
would otherwise pass the count check.

### 3.5 The aggregate arm is an addition, and a sound one — PASS

A3 states a per-SKU condition; A14 states an aggregate one
("`sum(inventory_item.stock)` … equals the quantity derived from truth events").
R1b requires **both**. This is strictly stronger than either authority alone and
cannot weaken the gate: a per-SKU error pair that cancels in the aggregate is
still caught by the first arm, and an aggregate drift that somehow evaded the
per-SKU arm is caught by the second. Satisfying both satisfies A3 and A14
simultaneously, so the two wordings cannot be played against each other.

### 3.6 Sign convention — PASS

A6 defines `gap = inventory_item.stock - SUM(quantity_delta)`. R1a prints
`variance` as `event_remaining - snapshot_stock`, the negation. This is not a
deviation: R1 tests **equality**, and equality is sign-symmetric. R1a's variance
is a diagnostic column for a human reader, and its sign is stated in the column
name and in the surrounding comment. The assertion in R1b uses `<>`, not a
threshold, so no sign can slip through.

### 3.7 Overlay hygiene is proved, not assumed — PASS with finding R1-1

A2 requires overlay deltas to be `0`. The accepted implementation enforces that
with `ck_overlay_zero_delta` (A11, L82–L86):

```text
(event_type NOT IN ('reserve','release','move','channel_commit','quarantine'))
OR (quantity_delta = 0)
```

A1 defines `OVERLAY` as those five **plus** `reverse` when the reversed event is
itself `OVERLAY`. The constraint does not cover that sixth case. A `reverse` row
whose `reverses_event_id` points at a `reserve` and whose `quantity_delta` is
non-zero is therefore **accepted by the schema while violating A2**, and because
R1 sums every delta with no type filter (§3.2), that row flows straight into
`event_remaining`. It could be masked by a compensating error elsewhere and
still produce `R1-zero`.

R1c closes this at the gate with four arms:

- **(a)** `ck_overlay_zero_delta` exists on this database as a CHECK constraint
      (`pg_constraint.contype = 'c'`), so arm (b) is schema-backed and not only
      query-backed;
- **(b)** zero rows of the five implemented overlay types carry a non-zero delta;
- **(c)** zero `reverse` rows whose reversed event is an overlay type carry a
      non-zero delta — the A1 clause the constraint does not enforce;
- **(d)** zero `reverse` rows with a dangling `reverses_event_id`, because (c)
      is unevaluable if the reversed event cannot be resolved.

A detail statement then prints `pg_get_constraintdef(...)` so the audit records
the predicate as it actually exists on the target database rather than as this
review quotes it.

R1c is evaluated **before** R1b, together with R1d, because both are
preconditions for R1b's zero meaning "snapshot equals truth". Under
`ON_ERROR_STOP` the first failure aborts the transaction, so a failed
precondition can never be followed by a printed verdict. The harness proves the
ordering: `_inject_overlay_reverse_violation` produces
`f2_gate_r1c_overlay_event_has_a_non_zero_delta` and neither `R1-zero` nor
`overlay-deltas-are-zero` appears in that run's output.

> **Finding R1-1 (P2, recorded for an owner decision — not a stop for this
> packet).** `ck_overlay_zero_delta` in
> `services/api/app/inventory_truth/models_truth.py` L82–L86 does not enforce
> frozen `DESIGN.md` L20–L21 and L29–L31 for the conditional `reverse` member of
> `OVERLAY`. Closing it in the schema is an application-code and frozen-contract
> matter, outside this packet's authority, and at step 5 it is unreachable
> anyway: the pinned tenant has zero event rows (§3.9). It becomes reachable
> under the later receive unlock, where `reverse` rows are written. The gate
> compensates for it now; the schema should be reconciled with A1 in a named
> slice.

### 3.8 One stock row per SKU is proved, not assumed — PASS

R1b's per-SKU comparison is equivalent to A9 **only if** `inventory_item` holds
at most one row per `(shop_id, sku)`. `reconcile_shop()` pops each SKU from its
event map as it walks the item rows, so a second row with the same SKU would be
compared against `0`; R1b would compare it against the full event sum. The two
readings disagree, and R1b's is the looser.

The accepted schema forecloses this: A12 declares `uq_inventory_shop_sku` on the
model and A13 creates it in the reviewed PostgreSQL DDL. R1d proves both halves
against the target database rather than trusting the model — the constraint
exists, `contype = 'u'`, and its column list is exactly `shop_id,sku` in that
order (read from `pg_constraint.conkey` with `WITH ORDINALITY`, so column order
is checked and not inferred) — and that the pinned tenant's data agrees
(`count(*) = count(DISTINCT sku)`). If the constraint were absent on the target,
R1d fails closed and R1b's equivalence claim is never relied upon.

### 3.9 Trivial-zero honesty — PASS

At step 5 the pinned tenant has no envelope rows: D-042 recorded the staging
business tables as empty, D-045 decision 4 defers the receive, and this packet
performs **no** A7/MIGRATION.md §4 backfill — steps 1–8 write only the cutover
row. R1 therefore compares an empty snapshot against an empty ledger, and its
zero is trivial in exactly the sense plan §5 records for R2 and R3. Plan §5
names only R2 and R3 as trivial; R1 is in the same position at this evaluation
point and the audit must say so.

R1e prints `r1_snapshot_rows_examined`, `r1_event_rows_examined`,
`r1_snapshot_distinct_skus`, `r1_event_distinct_skus`,
`r1_snapshot_stock_sum` and `r1_event_delta_sum` so the audit entry records
"trivial zero over N rows" rather than presenting R1 as a reconciliation of live
stock. The harness asserts all of them are `0` on the positive path. If either
row count were non-zero at step 5, something outside this packet wrote to the
envelope and the attempt stops under S6.

R1 becomes substantive when re-run under the later receive unlock, and again as
F4 at step 7 — where it is still expected to be trivial, because step 6 changes
only `status` and `opened_at`.

### 3.10 Determinism and failure behaviour — PASS

- The whole gate runs inside one `BEGIN; SET TRANSACTION READ ONLY` with
  `SET LOCAL statement_timeout` and `SET LOCAL lock_timeout`, so R1 cannot
  write and cannot hang. A timeout aborts the transaction and exits non-zero:
  **timeout is not green** (plan §5, S4). The harness proves it by holding
  `ACCESS EXCLUSIVE` on `inventory_event` from a second connection and asserting
  `lock timeout` in stderr with no `R1-zero` in stdout.
- Both CTEs are ordered by nothing and aggregated by `GROUP BY sku`, so the
  result is order-independent. `SUM` over `INTEGER` is exact; there is no float
  anywhere in R1, so no rounding can vary between runs. The harness runs
  `05-r1-r7.sql` twice over unchanged state and compares every column in
  `GATE_COLUMNS`, not merely the exit codes.
- The failure branch is `current_setting('stashtab_f2.<name>')`, an unrecognised
  configuration parameter. It names the exact invariant, cannot be swallowed by
  an error handler, and produces a non-zero psql exit under `ON_ERROR_STOP`.
- `:'cutover_shop_id'` is quoted as a literal, so the shop id is a bind-style
  string constant and cannot be reinterpreted as SQL. Guards G1 and G1b
  double-enter it and require both copies to be the pinned literal.

## 4. Deviations from the frozen text

| # | Deviation | Justification | Risk |
| --- | --- | --- | --- |
| 1 | R1b adds an aggregate equality arm alongside A3's per-SKU arm | Satisfies A3 and A14 at once; strictly stronger than either | None — cannot weaken the gate |
| 2 | `::bigint` widening of `SUM(quantity_delta)` and `stock` | Prevents aggregate overflow on a large ledger; equality-preserving | None |
| 3 | R1a prints `quantity_acquired` in a column named `not_in_r1` | Makes A4's exclusion visible instead of implicit | None |
| 4 | R1c arm (c)/(d) extend overlay hygiene past `ck_overlay_zero_delta` | Enforces A1/A2 as written, which the accepted constraint does not | None at step 5 (zero rows); substantive later |
| 5 | R1d and R1c evaluated before R1b | Preconditions must hold before a verdict is meaningful | None |
| 6 | R1e context columns | Honest trivial-zero evidence | None |

No deviation narrows, re-scores, or weakens any approved zero condition.

## 5. What this review did not do

It did not execute anything against staging, Neon, Railway or Clerk. It did not
edit frozen text, application code, schema, privileges, or flags. It did not
perform a receive. It did not re-derive R2–R7, which are covered by the bounded
packet review in `REVIEW-F2-CUTOVER-EXECUTION-PACKET.md`. Its execution evidence
is the disposable PostgreSQL 16 harness, whose results are recorded in
`CHECKPOINT-F2-CUTOVER-EXECUTION-PACKET.md` §4.
