# Proposed Contract Amendment 1.1.0 — Outbound Canonical Keys and Migration Envelope

**Parent contract:** `STASHTAB-INVENTORY-TRUTH-001` version `1.0.0` (frozen 2026-08-20)
**Status:** `PROPOSED — AWAITING HUMAN VOTE (FREEZE DEFERRED PENDING THIS AMENDMENT)`
**Proposed:** `2026-08-23`
**Amendment identifier:** `STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.1.0`
**Proposed resulting version:** `1.1.0`
**Design source:** `DIRECTIVE-SLICE-02.md` v3; review record
`reviews/SLICE-02-PLANNING-REVIEWS.md`
**Rule followed:** CONTRACT §6 — versioned proposal, independent review
(completed in the slice-02 planning cycle), updated acceptance tests,
named human approval, new freeze record. **The frozen bodies are not
edited by this proposal.**

## 1. Statement of change

Add outbound (`sell`) canonical idempotency keys and their supporting
structures to the frozen contract's canonical-key examples and migration
envelope. Grammar is unchanged:
`{source}:{shop_id}:{source_pk}` with the single permitted suffix
`:gen:{n}` for generation-scoped sources. No other grammar exists.

## 2. Required statement 1 — every new canonical key

All keys are strings over `[A-Za-z0-9_.:-]` only (letters, digits,
underscore, dot, colon, hyphen), maximum length 255 (matching
`idempotency_key VARCHAR(255)` shipped in slice-01 schema). `shop_id` is
the tenant UUID (36 chars). Numeric PKs are decimal integers.

| Key | Field structure | Scope | Example |
|---|---|---|---|
| POS/show sell | `sell_sale:{shop_id}:{sale_id}` | shop + sale line row | `sell_sale:9b1f…-a3:4821` |
| Shopify pull sell (full or short) | `sell_shopify_order_line:{shop_id}:{order_id}:{line_id}` | shop + native order line | `sell_shopify_order_line:9b1f…-a3:5590342211:98765432` |
| Confirmed-return receive | `{return_source}:{shop_id}:{return_record_id}` where `return_source ∈ {return_refund, return_sale}` | shop + return record row | `return_refund:9b1f…-a3:17` |

Over-sale short sells reuse the pull key verbatim (no suffix). Reversals
and compensating events create NEW events with their own keys (below);
they never mutate originals.

## 3. Required statement 2 — enforcing table and constraint per key

| Key class | Table | Enforcing unique constraint |
|---|---|---|
| POS/show sell | `inventory_event` | `uq_event_shop_idemkey (shop_id, idempotency_key)` |
| Pull sell (full/short) | `inventory_event` | same |
| Return receive | `inventory_event` | same |
| Observation ledger (retry arbitration) | `inventory_channel_observation` (new, TruthBase) | `uq_obs_shop_channel_ref (shop_id, channel, channel_ref)` |
| Refunds / returns / exceptions | `refund_record`, `return_record`, `inventory_exception` (new, TruthBase) | own `(shop_id, id)` plus composite FKs to parents |

All five tables extend `TruthBase` and `TRUTH_TABLE_NAMES`; startup
`create_all` can never create them (MIGRATION.md locked path preserved).

## 4. Required statement 3 — per-source key rules

- **POS/show:** one event per Sale line, key from that row's `sale.id`;
  all lines of one checkout share a receipt correlation string recorded on
  the observation ledger row (advisory only; it arbitrates nothing).
- **Shopify pull:** one event per native order line;
  `{order_id}:{line_id}` is durable across worker retries.
- **Over-sale (Q > S):** SAME pull key; delta = −S actually removed;
  reason marker `short:{Q−S}`; one critical `inventory_exception` row in
  the same transaction.
- **Reversal:** new event, `event_type='reverse'`,
  `reverses_event_id` → original `(shop_id, inventory_event.id)` via the
  shipped composite FK. Key: `reverse_{orig_source}:{shop_id}:{orig_pk}[:seq]`
  where `:seq` (decimal, starting 2) disambiguates multiple reversals of
  one original; seq 1 may omit the suffix.
- **Confirmed return:** one positive receive-class event keyed per §2;
  written atomically with its `return_record`.
- **Exception register rows** are not keyed events; uniqueness is
  `(shop_id, kind, channel_ref, status='open')` partially enforced by
  application check at insert (one open exception per channel line).
- **Compensating event** (resolution flow): always
  `event_type='reverse'` referencing the duplicate pair's original event;
  key follows the reversal rule.

## 5. Required statement 4 — behaviour under retry/concurrency/partial/restart/restock

- **Retries:** identical key → existence check finds both rows consistent →
  no-op (five-step rule unchanged).
- **Concurrent workers:** PostgreSQL unique constraints serialize; loser's
  savepoint rolls back before any snapshot write; treated as retry no-op.
- **Partial line processing:** each line commits independently; a failed
  line records `failed_permanent` (if contradictory) or defers, and the
  batch continues — no partial pairs persist.
- **Restarts:** nothing in memory; state lives in the ledger/events; a
  restarted worker re-reads committed rows and no-ops.
- **Later restocking:** key classes never encode current stock, so a
  restock cannot change any key or delta; re-pulls after restock hit the
  same committed key and no-op. A contradictory computed delta raises
  failed_permanent instead of writing.

## 6. Required statement 5 — slice-01 receive/backfill keys

**No change.** Receive sources (`staging_commit`, `purchase_record`),
backfill keys, opening/shrinkage `:gen:1` usage, and the five-step rule
are untouched; slice-01 acceptance evidence (14/14 PG criteria ×2, recon
zero) remains valid because no receive-path key, table, or constraint is
altered. This amendment adds sources; it does not redefine existing ones.
No separate decision required on this item.

## 7. Required statement 6 — legacy/existing rows

Pre-slice-02 Sales and events get no observation-ledger backfill and no
key changes; they are never rewritten. At slice-02 cutover per shop:
freeze → drain outstanding online-pull queue under legacy rules → run gap
reconciliation (slice-01 mechanism absorbs drained decrements as proven by
PG acceptance criterion 11) → lift freeze with dual-write. History stays
append-only forever.

## 8. Required statement 7 — compensating references

A compensating event sets `reverses_event_id` (+ `shop_id`) referencing
the original event's composite key. Originals are immutable: no UPDATE or
DELETE path exists on truth tables in any flow this amendment enables;
append-only refund/return tables additionally carry DB-level REVOKE/
trigger enforcement with a negative test.

## 9. Required statement 8 — why no double quantity / stock-dependence

Quantity derives solely from stored `quantity_delta`. Every new key maps
to exactly one real-world occurrence (line, order-line, or confirmed
return record); duplicates collide on the unique constraint and no-op.
Short sales store the removed quantity, not the requested one, so
reconciliation arithmetic never reads live stock; the shortage lives in
the exception register. Restocks add NEW positive-keyed events rather than
altering old ones. Therefore neither double quantity nor stock-dependent
reconciliation can arise from this amendment.

## 10. Required statement 9 — exact frozen clauses affected

Frozen files are NOT edited now. On approval, the next freeze record
(Contract → `1.1.0`) will incorporate:

- `DESIGN.md` §2 (canonical key): append the three outbound key forms and
  the reversal key rule to the canonical examples list. Grammar sentence
  unchanged.
- `MIGRATION.md` envelope/§Order step 7: replace "Sell/Shopify dual-write
  is a later PR" note with pointer to the unlock ordering (outbound →
  adjust → production cutover); extend the additive-DDL envelope list with
  the four new tables and the observation-ledger constraint.
- `TESTS.md`: add the twelve slice-02 acceptance tests (directive §8).

The diff below shows exactly these insertions.

## 11. Required statement 10 — implementation compatibility & rollback evidence

Required during slice-02 implementation acceptance:

- PG acceptance harness extension green twice on fresh databases
  (cross-channel race, scheduler overlap, over-sale retry-after-restock,
  freeze-drain ordering, create_all prevention for the four new tables).
- SQLite suite green with no receive-path regression (slice-01 tests
  byte-for-byte unchanged and passing).
- Rollback drill: cutover-row flip refreezes outbound; drain-under-legacy
  rules then reconcile-zero checkpoint before dual-write resumes.
- Append-only negative test passes at DB level.

## 12. Exact proposed amendment diff (unified, applied only after approval)

```diff
--- a/docs/inventory-truth-v1/DESIGN.md          (§2 Canonical idempotency keys)
+++ b/docs/inventory-truth-v1/DESIGN.md
@@
-{source}:{shop_id}:{source_pk}
+{source}:{shop_id}:{source_pk}
+
+Canonical sources (complete list):
+  receive-side (v1.0.0):
+    staging_commit        staging_commit:{shop_id}:{staging_item_id}
+    purchase_record       purchase_record:{shop_id}:{purchase_record_id}
+    opening|shrinkage     {source}:{shop_id}:{sku_or_item}:gen:1
+  outbound-side (AMENDMENT-1.1.0):
+    sell_sale             sell_sale:{shop_id}:{sale_id}
+    sell_shopify_order_line
+                          sell_shopify_order_line:{shop_id}:{order_id}:{line_id}
+    return_refund         return_refund:{shop_id}:{return_record_id}
+    return_sale           return_sale:{shop_id}:{return_record_id}
+    reverse               reverse_{orig_source}:{shop_id}:{orig_pk}[:seq]
+
+Permitted characters [A-Za-z0-9_.:-]; max length 255. The ONLY
+generation suffix remains :gen:{n}. Over-sale short sells reuse
+sell_shopify_order_line verbatim; the unsatisfied quantity lives in
+inventory_exception, never in a key.
```

```diff
--- a/docs/inventory-truth-v1/MIGRATION.md       (additive envelope + order step 7)
+++ b/docs/inventory-truth-v1/MIGRATION.md
@@
 The approved migrator is the only process that imports that module and
 applies DDL.
+Slice-02 additions (same discipline): inventory_channel_observation,
+refund_record, return_record, inventory_exception join TRUTH_TABLE_NAMES.
+Unique arbitration: uq_obs_shop_channel_ref (shop_id, channel, channel_ref).
@@
-7. Sell/Shopify dual-write is a later PR.
+7. Sell/Shopify dual-write is a later PR gated on AMENDMENT-1.1.0;
+   shipping order: outbound slice -> adjust slice -> production cutover.
```

```diff
--- a/docs/inventory-truth-v1/TESTS.md           (acceptance tests section)
+++ b/docs/inventory-truth-v1/TESTS.md
@@
 ## Slice-01 acceptance tests
 ...
+
+## Slice-02 outbound acceptance tests (AMENDMENT-1.1.0)
+Twelve tests per DIRECTIVE-SLICE-02 §8: POS/pull dual-write + retries,
+scheduler-overlap arbitration, cross-channel duplicate fail-visible
+exception, distinct-sales non-merge, over-sale short + exception +
+restock-stable retries, contradictory-retry failed_permanent, batch
+continuation, insufficient-stock rejection, append-only DB-level
+negatives, atomic confirmed returns, freeze/rollback drill with drain
+checkpoint, PG harness extension in blocking CI.
```

## 13. Before/after key mapping

| Aspect | Before (v1.0.0 frozen) | After (1.1.0 if approved) |
|---|---|---|
| Receive keys | `staging_commit:…`, `purchase_record:…`, `:gen:1` gaps | unchanged |
| POS sell | none (no sell events) | `sell_sale:{shop}:{sale_id}` |
| Pull sell | none | `sell_shopify_order_line:{shop}:{order}:{line}` |
| Short sell | none | same key as full pull sell |
| Return positive | none | `return_refund|return_sale:{shop}:{return_id}` |
| Reversal | reserved vocabulary only | `reverse_{orig_source}:{shop}:{pk}[:seq]` |
| Suffixes allowed | `:gen:{n}` only | `:gen:{n}` only (unchanged) |

## 14. Duplicate-suspicion rules

Alert signals permitted to CREATE a review exception: per-SKU window
comparison showing POS-observed units + pull-observed units exceeding
snapshot-delta evidence; an open over-sale exception on the same line; a
vendor-initiated inquiry referencing two observations.

Hard prohibition: SKU similarity, amount similarity, timestamp proximity —
alone or combined — can NEVER automatically link, suppress, reverse, or
compensate any observation. Identical-twin sales stay independent.

Compensating events require, in order: a verified provider link (future
native integration carrying counterpart identity), a trusted
StashTab-created link (system minted both sides), OR explicit authorized
human resolution recorded in the registry with actor identity, timestamp,
and rationale. Every resolution writes an audit record (actor, decision,
both observation refs) before the compensating event commits.

## 15. Seven bounded decisions — plain language and classification

1. **Observation ledger vs lighter index.** Keep the small extra table
   that remembers every observed sale line so retries and overlapping
   workers are safe, versus relying only on a new database index.
   *Class: required before slice-02 implementation* (schema shape).
2. **Manual "rung up at counter" linkage UI timing.** When do we build the
   screen where a vendor says "this online order was also sold at my
   counter"? The slice stores resolutions either way.
   *Class: required before production cutover* (resolutions must be
   possible before go-live).
3. **Over-sale alert routing.** Critical push notification vs dashboard-
   only when an oversell is detected.
   *Class: required before slice-02 implementation* (notification wiring
   ships with the slice).
4. **Repeated oversells stack exceptions.** Confirm that a second oversell
   of the same SKU creates another open exception rather than updating
   one. Default: stack.
   *Class: required for this amendment vote* (defines exception-register
   semantics referenced by the contract text).
5. **POS insufficient-stock HTTP status.** Which error code the API
   returns (409 recommended) when a cart exceeds stock.
   *Class: required before slice-02 implementation.*
6. **"Resalable" definition owner.** Who defines the condition threshold
   for accepted returns — fixed rule or vendor policy.
   *Class: required before production cutover* (returns only matter once
   live).
7. **Open-critical retention policy.** How long unresolved critical
   exceptions may exist before blocking further cutover steps for that
   shop.
   *Class: non-blocking follow-up* (operational policy; default "stack,
   block only at cutover gates" is safe until decided).

Nothing else is open. All alternatives outside these seven were resolved
in the correction pass or are prohibited outright.

## 16. Bounded consistency check against frozen slice-01 contract/evidence

Checked against CONTRACT v1.0.0 §3 decisions 1–8, MIGRATION.md locked
path/order/backfill sections, TESTS.md, and SLICE-01-PG-ACCEPTANCE
evidence:

1. Key grammar unchanged; only source names added. CONSISTENT.
2. Five-step collision rule reused verbatim; no new collision semantics.
   CONSISTENT.
3. Slice-01 receive/backfill keys untouched (§6 above). CONSISTENT.
4. Migrator-only creation pattern extended, not bypassed (create_all gate
   test extended to four new tables). CONSISTENT.
5. Quantity equation and reconciliation method unchanged; exceptions live
   outside the equation. CONSISTENT.
6. Freeze/cutover order extended with explicit adjust-before-production
   dependency already recorded in GATES.md. CONSISTENT.
7. No clause of the frozen bodies is edited by this proposal; the diff
   applies only upon approval and re-freeze at 1.1.0. CONSISTENT.
8. Acceptance-test additions do not weaken existing slice-01 tests.
   CONSISTENT.

Result: 8/8 checks pass; no conflict found with frozen slice-01 wording
or evidence.

## 17. AMENDMENT APPROVED — human vote recorded

**Vote:** APPROVED by human owner, 2026-08-23.
**Resulting contract version:** `1.1.0`.

Binding interpretations and decisions recorded with the vote:

1. **Oversale exception semantics.** A retry/replay of the same canonical
   Shopify order-line key reuses the existing exception — never stacks.
   A distinct canonical order-line observation may create its own
   exception. Multiple genuinely distinct unresolved oversales accumulate.
   Exception creation/lookup must be concurrency-safe and idempotent.
2. **Observation ledger retained** (not replaced by a lighter index):
   required for durable source observation, retry arbitration, exception
   linkage, and audit evidence.
3. **Oversale alert routing.** Always create the in-application critical
   exception. Web Push only when existing security/configuration gates
   are satisfied AND the vendor enabled it. Delivery failure never
   removes, acknowledges, or resolves the exception. SMS out of scope.
4. **POS insufficient stock → `409 Conflict`**, stable machine-readable
   error code, zero partial Sale/snapshot/lot/event mutation.
5. **Manual-resolution workflow required before production outbound
   cutover.** Until it exists, no automated similarity-based compensation
   is permitted.
6. **Resalable decision owned by the vendor.** Authorized owner/staff
   record the physical inspection outcome: actor, shop, timestamp,
   original outbound reference, returned quantity, outcome. Only
   confirmed whole-unit `resalable` outcomes increase inventory.
7. **Critical-exception retention is a named policy follow-up.** Until a
   formal policy exists, unresolved exceptions and their audit history
   are never automatically deleted.

These interpretations bind the implementation directive and any later
amendment interpretation of this packet.
