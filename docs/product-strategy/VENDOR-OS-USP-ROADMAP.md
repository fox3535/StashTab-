# StashTab vendor OS — USP and inventory roadmap

**Status:** approved product direction; implementation remains gated  
**Recorded:** 2026-08-14  
**Product boundary:** vendor-only SaaS; no consumer marketplace

## Positioning

StashTab is the operating system for card vendors from acquisition and physical
custody through sale, reconciliation, profitability, and informed exit decisions.

> Know what you own, where it is, what it truly cost, what it is worth, how
> quickly it can sell, and what action to take next.

Scanning, catalog lookup, portfolio value, price charts, basic inventory, POS,
and channel sync are table stakes. Differentiation comes from joining trusted
physical inventory, acquisition economics, vendor operations, accounting
evidence, and governed advisory intelligence.

## Reuse-before-build rule

Before implementing a roadmap item, inspect `PLAN.md`, `FEATURE_PARITY.md`,
current models, APIs, UI, tests, and the vendored Python brain. Extend the
existing implementation when it preserves the contracts and produces a simpler
source of truth. Do not create a parallel inventory, sales, pricing, show,
reconciliation, Shopify, or Watch subsystem.

When an existing implementation is weaker than the approved target, migrate it
incrementally with compatibility, backfill, reconciliation, rollback, and
human-approved schema evidence. Do not silently replace working behavior.

## Capability reconciliation

### Existing foundations to preserve and optimize

- `InventoryItem` is the current shop/SKU quantity and price snapshot.
- `StagingItem` is the existing intake gate.
- Persistent SKU reuse and weighted-average cost already exist in Python.
- `PurchaseRecord` provides a basic shop/SKU acquisition record.
- `Sale` records price, profit, fees, net revenue, transaction type, trade
  value, show session, and reconciliation status.
- Mobile POS supports cash, trade, and card-as-payment-method checkout.
- Pending trades and weighted trade-cost distribution already exist.
- Show sessions, show P&L, price captures, restickering, paperweight alerts,
  Collectr reconciliation, Shopify outbox/pull queue, labels, and reporting exist.
- Portfolio Watch and Market Watch have planning-only contracts under
  `docs/security-assurance-v1/`; do not duplicate them here.

### Known gaps in the current foundations

- Inventory quantity is mutable without an immutable inventory-event ledger.
- Purchase records are SKU-based rather than complete acquisition lots linked
  to units, sources, evidence, and later sales.
- Weighted-average cost is a snapshot; lot history cannot yet explain every
  unit's acquisition-to-exit economics.
- Physical locations, reservations, channel commitments, quarantine, damage,
  loss, return, and cycle-count states are incomplete.
- Show sessions lack cash-drawer opening, counted close, variance,
  denominations, approvals, and immutable adjustments.
- `ShowPriceCapture` is a sticker-price snapshot, not licensed point-in-time
  market observation history.
- Monetary values use floats; financial-ledger work must use exact decimal or
  integer minor units and migrate safely.
- Watch analysis runs, evidence, outcomes, and model/rule versions are not built.

## Approved USPs

1. **Inventory truth engine** — auditable identity, custody, location,
   availability, channel commitment, reconciliation, and adjustment history.
2. **Acquisition-to-exit economics** — lot cost, cash/trade allocation, fees,
   holding period, realized margin, and opportunity cost.
3. **Show-floor operating system** — mobile POS, show kits, cash/trade
   settlement, show P&L, and post-show inventory/cash reconciliation.
4. **Confidence-aware card resolution** — frozen local-match, budgeted
   JustTCG, human-review, and verified-write hierarchy.
5. **Vendor Portfolio Watch** — cost, value, liquidity, concentration,
   holding period, estimated time to sell, and evidence-backed actions.
6. **Market Watch connected to owned inventory** — licensed market signals
   translated into shop-specific exposure and opportunity.
7. **Accounting bridge** — immutable operational subledger, cash sessions,
   processor reconciliation, adjustments, and accountant-ready exports.
8. **Exception-first automation** — routine automation, deterministic
   abstention, human alerts, evidence, liveness, and governed learning.

## Optimized inventory architecture

Keep `InventoryItem` as a query-optimized current snapshot during migration.
Add authoritative append-only records underneath it rather than introducing a
second competing inventory manager.

### Identity and acquisition lots

Canonical identity comes from the frozen card-resolution contract. Each
physical acquisition is a **separate immutable lot**, including repeated
buys of the same SKU at different costs (D-008). Keep
`InventoryItem` weighted-average cost as the current snapshot. Do not merge
or erase lot history. Backfill from `PurchaseRecord`; do not delete that
history until a reviewed migration says otherwise.

COGS selection (FIFO, weighted average, or specific identification) is a
deferred accountant gate and does not block lot capture.

Parent **receipt/transaction** identity (D-008): one checkout is one
receipt containing one or more existing `Sale` lines. Do not replace the
sales system.

### Inventory events, availability, and location

Record receive, merge, split, move, reserve, release, channel-commit, list,
sell, return, damage, loss, quarantine, count, adjust, and reverse events. Each
event has shop, actor, reason, correlation/idempotency key, timestamp, quantity
delta, location, and evidence. Corrections use reversing events.

Derive or transactionally maintain `InventoryItem.stock`, cost, and availability
from accepted events. Separate on-hand, reserved, channel-committed, in-transit,
sold, returned, quarantined, damaged, and missing so one quantity cannot be
promised twice. Support shop, room, case, bin, binder, show kit, and pull/packing
locations through scan-supported, tenant-scoped events.

### Reconciliation and decision features

Extend existing Collectr and Shopify reconciliation. Add cycle counts and
event-ledger checks without creating another recon engine. Every job must account
for its source count and produce zero unaccounted items.

Compute aging, turnover, realized/unrealized margin, liquidity, spread, sales
velocity, source disagreement, price trend, concentration, resticker need,
estimated time to sell, and opportunity cost from point-in-time evidence. Agents
explain/rank these features; they do not invent or rewrite them.

## Phased dependency order

### A — Card identity and checkpoint gates

Finish the notification checkpoint and `card-resolution-core-v1` gates.

### B — Inventory truth foundation

Plan and review acquisition lots, events, locations, reservations, cycle counts,
backfill, exact-money migration, and compatibility. Build only after a named
human unlocks the slice and migration plan.

### C — Vendor financial operations

Extend `Sale`, `PendingTrade`, and `ShowSession` with a parent receipt
identity (D-008), cash sessions, and an immutable operational subledger. Preserve show P&L until verified ledger-derived
results match it. This is accounting support, not a general-ledger claim.

### D — Market-data foundation

Use only licensed point-in-time observations with freshness, source identity,
deduplication, and variant/condition separation. Existing show sticker captures
remain vendor snapshots and cannot be relabeled as market history.

### E — Deterministic Portfolio/Market Watch

Ship auditable metrics and abstention before agent narratives. Evaluate against
time-based holdouts and prevent future-data leakage.

### F — Governed advisory agents

Add evidence-citing sell/hold/watch, fatigue, concentration, and complementary
inventory analysis. Advisory only: no automatic pricing, listing, buying,
selling, transfer, or inventory mutation. Learning follows
`docs/security-assurance-v1/LEARNING-LOOP.md`.

## Success measures

- Inventory variance and unaccounted-item rate
- Duplicate/oversell prevention events
- Percentage of units with verified identity, lot cost, and location
- Intake-to-sell cycle time, turnover, and aged-capital reduction
- Gross margin by acquisition source, channel, and show
- Cash-session variance and reconciliation age
- Watch coverage, abstention, calibration, overturn, and horizon accuracy
- Human-review queue age and false-accept rate

Metrics remain shop-scoped and cannot silently turn advisory signals into
release gates or automated inventory actions.
