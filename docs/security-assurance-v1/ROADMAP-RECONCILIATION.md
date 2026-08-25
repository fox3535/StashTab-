# Roadmap reconciliation (planning)

**Canonical product direction:**
`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md` (D-007). Do not duplicate
USPs or the roadmap here.

**Reuse-before-build:** extend existing FastAPI inventory, staging, purchase,
sales, show, pricing, reconciliation, resticker, reporting, and Shopify
systems. Parallel replacements are blocked.

Implementation of new schemas, payments, Watch, jobs, and models remains
blocked.

## 1. Already implemented (preserve)

- `InventoryItem` shop/SKU quantity and price snapshot
- `StagingItem` intake gate
- Persistent SKU reuse and weighted-average cost
- `PurchaseRecord` basic shop/SKU acquisition log
- `Sale` price, profit, fees, net, tender type, trade value, show session,
  reconciliation status
- Mobile POS cash, trade, and card-as-**payment-method label**
- Pending trades and weighted trade-cost distribution
- Show sessions, show P&L, `ShowPriceCapture` sticker snapshots
- Resticker queue, paperweight alerts, Collectr recon, Shopify outbox/pull,
  labels, reporting
- Clerk SaaS billing shell, shop create, invites
- Frozen card-resolution **contract** (core build still blocked)

Do not rewrite these as unimplemented.

## 2. Existing but requiring optimization

- Mutable `InventoryItem.stock` without an append-only inventory-event ledger
- `PurchaseRecord` not yet backfilled into immutable per-acquisition lots
  (D-008: lots must not be merged; weighted-average snapshot stays)
- Incomplete location, reservation, channel-commit, quarantine, damage,
  loss, return, and cycle-count states
- Show sessions without cash-drawer open/count/variance/approval
- `ShowPriceCapture` is not licensed market-observation history
- Float money on live financial columns
- Collectr/Shopify recon exist; they need event-ledger and cycle-count
  checks, not a second recon product
- POS `card` label is not provider-captured CHD
- Fail-open shop identity (`deps.py`, `clerk.py`, `shops.py`)

## 3. Genuinely new (still blocked)

- Append-only inventory events under the existing snapshot
- Acquisition lots (immutable; backfill from `PurchaseRecord`; keep
  weighted-average snapshot)
- Parent receipt/transaction wrapping existing `Sale` lines (D-008)
- Inventory **reserve / release** events for electronic tender
- Exact decimal / integer-minor-unit money migration
- Cash sessions and immutable operational subledger **on** `Sale` /
  `PendingTrade` / `ShowSession`
- Licensed point-in-time market observations
- Watch analysis runs, evidence, outcomes, rule/model versions
- Deterministic Watch metrics, then advisory agents
- Vendor-merchant Stripe/PayPal capture (hosted/terminal) and webhooks

## 4. Blocked by earlier dependencies or human gates

| Capability | Blocked by |
|---|---|
| Inventory truth (lots, events, locations, receipt parent) | Notification leftovers; `card-resolution-core-v1`; fail-closed identity on **reads and writes**; named **implementation unlock** |
| Cash sessions / subledger | Inventory-truth mapping; fail-closed identity; named unlock |
| Electronic card capture | Named payments unlock; fail-closed identity. PCI and provider **production** config are deferred professional gates, not planning blockers |
| Market-data foundation | Named unlock. **License** is a deferred professional gate |
| Deterministic Watch | Inventory truth; marks if licensed data exists, else named deferral of marks |
| Advisory agents | Deterministic Watch; named unlock; no auto-reprice |
| Outcome learning | Advisory agents; offline evals |

**Deferred professional gates (do not block this planning package):**
final COGS method; trade-credit/stored-value treatment; market-data
licensing; PCI determination; Stripe/PayPal production configuration;
production migration approval.

Security-assurance slices must follow this order. They must not invent a
parallel POS or Watch stack ahead of inventory truth.
