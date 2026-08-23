# Market Watch contract (planning only)

**Contract ID:** `STASHTAB-MARKET-WATCH-001`  
**Version:** `0.1.0-draft`  
**Status:** `PROPOSED — NOT FROZEN`  
**Implementation blocked.**

Canonical phasing is `docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`.
Existing `ShowPriceCapture` rows are vendor sticker snapshots and **must
not** be relabeled as licensed market history. Connect licensed signals to
**this shop’s** owned inventory only.

## Purpose

Describe **market** conditions for catalog identities using licensed
observations. Advisory only. Not a consumer storefront feed.

## In scope

- price and volume trends
- listing supply
- liquidity and spread
- acceleration / deceleration
- market-source divergence
- low-volume pump risk
- fatigue / reversal signals
- reprints, rotations, bans, releases, tournaments, and other **recorded**
  market events
- confidence, freshness, and abstention rules

## Out of scope

- Guaranteed prices or “will hit” claims
- Auto-trading or auto-repricing inventory
- Using another tenant’s private acquisition costs as market truth
- Scraping in violation of provider terms (license TBD)

## Freshness and abstention

Every published market view has an observation time and a freshness budget.
If identity, variant, condition, source freshness, liquidity, or source
agreement is insufficient, **abstain**.

Stale prices must not be treated as current. Duplicate sales must be
deduplicated. Survivorship (delisted cards vanishing from history) must not
silently inflate trends.

## Point-in-time

Feature computation for a timestamp T may use only observations with
`observed_at <= T`. Historical evaluations must not leak future prints,
future sales, or later agent recommendations.

## Licensing

Adapters stay implementation-blocked until a named unlock. **Which sources
are licensed** is a deferred professional gate (D-008), not a reason to
leave Market Watch unspecified. Do not scrape against terms. Do not
relabel `ShowPriceCapture` as market history. JustTCG budget reuse vs a
new contract is decided at unlock time from then-current licenses.

## Writes and identity

Fail-closed identity is an entry gate for Market Watch **reads and writes**
(observations, features, and any shop exposure view). Header shop-id is not
authorization.

`ShowPriceCapture` must not be used as a market-observation source.

Recommendations are **excluded by default** from market-observation
features. Inclusion needs a named human gate.

Point-in-time: features at T use only observations known at T (`observed_at`
and `recorded_at` both `<= T`). Do not value a historical position using
**current** marks unless the run’s `as_of` is now.
