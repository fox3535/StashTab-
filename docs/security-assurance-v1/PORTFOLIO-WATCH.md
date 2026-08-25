# Portfolio Watch contract (planning only)

**Contract ID:** `STASHTAB-PORTFOLIO-WATCH-001`  
**Version:** `0.1.0-draft`  
**Status:** `PROPOSED — NOT FROZEN`  
**Implementation blocked.**

Canonical inventory/Watch phasing is
`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`. This contract is the
advisory ruleset, not a second inventory product. Agents explain metrics
from existing inventory, purchases, sales, resticker, and show data; they
do not invent or rewrite them.

## Purpose

Help one approved tenant understand **its own** inventory and acquisition
history. Advisory only.

## In scope (deterministic metrics first; agent signals are Roadmap F)

Analysis of that shop’s positions using:

- acquisition cost and date (lot / cost basis)
- current estimated market value
- unrealized gain/loss
- price trend by approved horizons
- sales velocity and liquidity
- listing/sold spread
- supply changes
- data-source agreement
- inventory concentration
- holding duration
- estimated time to sell
- sell, hold, and watch **signals**
- confidence components
- supporting and conflicting evidence
- complementary portfolio/inventory opportunities
- subsequent outcomes (for later evaluation, not live training)

## Out of scope

- Automatically listing, pricing, purchasing, selling, transferring, or
  removing inventory
- Consumer marketplace recommendations
- Treating estimates as guaranteed values
- Training on another shop’s costs, actions, or outcomes without an explicit
  approved anonymization and aggregation policy
- Uncontrolled continual learning

## Confidence (separate values)

Store and evaluate separately (aligns with frozen card-resolution invariant 3
for identity vs price):

- identity confidence
- price confidence
- liquidity confidence
- trend confidence
- recommendation confidence

Do not collapse these into a single undocumented score.

## Recommendation record (required fields)

Every recommendation must include:

- time horizon
- evidence sources
- observation timestamps
- material missing data
- confidence components (as above)
- rule/model version
- expiration

After expiration, the signal is not current. UI must not present it as live.

## Abstention

The agent **must abstain** when identity, variant, condition, source
freshness, liquidity, or evidence agreement is insufficient. Abstention is a
first-class outcome, not a silent low score.

## Identity and lots

Cost basis is **immutable lots** (D-008), shop-scoped. Weighted-average on
`InventoryItem` is the snapshot only. Condition and variant mixing is
forbidden in a single lot without explicit breakdown.

## Writes and identity

Fail-closed identity (verified JWT, membership, **explicit authorized shop**)
is an **entry gate** for all Portfolio Watch **reads and writes**. Header
shop-id is not authorization.

Portfolio Watch may **read** that shop’s authorized current data and
**insert** analysis runs, recommendations, and evidence. It must not mutate
inventory quantities, list prices, Shopify outbox, resticker rows, or sales.

“Listing/sold spread” means **this vendor’s** sticker or Shopify list price
versus **this vendor’s** sold price — not a consumer marketplace listing.

“Complementary opportunities” means other SKUs **in the same shop**. Not
vendor-to-vendor matching.
