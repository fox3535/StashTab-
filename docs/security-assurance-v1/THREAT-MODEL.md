# Threat model (planning)

Not an authorization to test. Live auth facts from current code.

## Current verified auth (must not be papered over)

Source: `services/api/app/deps.py`, `services/api/app/auth/clerk.py`,
`services/api/app/routers/shops.py`.

- Unauthenticated `X-Shop-Id` selects a shop on most API routes.
- `X-Clerk-User-Id` is accepted without Bearer even when JWT issuer is set.
- Shop create / onboard / get / list members / invite do not use shop context.
- JWT members bind to `.first()` membership.

Payment reconciliation, cash close, Portfolio Watch, and Market Watch **must
not ship** on this identity model.

## Assets

Inventory, acquisition costs, cash-drawer counts, Shopify tokens, future
vendor merchant-account ids and webhook secrets, market observations,
recommendations, evaluation datasets, Clerk subscription billing.

## Adversaries

Unauthenticated API client, staff at shop A reading shop B, webhook forger,
insider, restore-of-prod-into-staging, market-data manipulator (wash sales /
low-volume prints), prompt or weight tampering in production.

## Abuses this plan must block (when implemented)

| Abuse | Control intent |
|---|---|
| Header shop-id reads another shop’s ledger, lots, or recs | Fail-closed JWT + `shop_id`; webhooks bind from signed provider mapping |
| Redirect treated as POS paid | Webhook signature + reconcile; no deduct until paid |
| Electronic tender deducts before paid | Reserve at start; sell only after webhook; release on fail/cancel/expiry |
| Replay webhook double-posts | Idempotent `shop_id + provider + event id` on the **receipt** |
| Merging same-SKU lots erases cost history | Immutable lots; WA snapshot only (D-008) |
| PAN in logs or DB | Hosted fields / terminals only |
| StashTab wallet / payout / escrow | Forbidden (not a marketplace) |
| Recommendation auto-sells inventory | Advisory-only write block |
| Cross-shop training on costs/outcomes | Default deny; policy gate |
| Future leakage in backtests | Point-in-time datasets |
| Circular learning from own recs | Exclude recs from market observations |
| Stale/duplicate/condition-mixed prices | Dedup, freshness, variant+condition keys |
| Staging uses restored prod keys | Scrub restore; ROE |
| Silent production prompt/weight change | Governed learning loop only |

## PCI-relevant threats

Skimming in StashTab UI, logging card fields, custom card forms. Mitigation:
never build a PAN form; specialist review before terminals.
