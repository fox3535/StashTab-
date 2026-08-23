# Security and compliance scope

## Product

StashTab is a **vendor-only** operating system for approved card businesses.

## In product scope

**Already live (preserve and optimize):** POS, inventory, intake/staging,
Shopify vendor-shop sync, Collectr recon, resticker, show sessions, reporting.

**Planning only (blocked):** cash-session fields, inventory events/lots,
Stripe/PayPal capture, Portfolio Watch, Market Watch, accounting subledger
migration.

**Out of product scope (withdrawn):**

- Consumer accounts that list or buy on a shared StashTab marketplace
- Meetup fulfillment as a StashTab marketplace mode
- Multi-vendor carts / marketplace shipping
- Marketplace seller payouts, escrow, wallets, buyer protection
- StashTab as merchant of record for vendor inventory sales

## Trust boundaries

```text
Vendor staff (browser / POS)
  -> FastAPI (shop_id) -> PostgreSQL tenant data

Vendor’s own customers
  -> pay the vendor (cash, or later vendor Stripe/PayPal)
  -> do not hold StashTab marketplace accounts

StashTab subscription billing (Clerk)
  -> separate domain from vendor POS payments

Market-data providers (future)
  -> FastAPI adapters -> immutable observations (licensed use TBD)
```

## Data classes

| Class | Handling |
|---|---|
| PAN/CVV/track data | Never store or log |
| Provider payment ids | Allowed (charge, refund, dispute, settlement ids on the **vendor’s** merchant account). Not a StashTab payout engine. |
| Cash counts | Shop-scoped; authorized reconcilers |
| Acquisition cost / lots | Shop-scoped; not shared across tenants |
| Market observations | Licensed terms TBD; immutable; point-in-time |
| Recommendations | Advisory; expire; not inventory writes |
| Evaluation datasets | Shop-scoped unless an approved anonymization policy exists |

## Compliance objectives

SOC 2 Type I later, after named owners. PCI **in analysis** for vendor POS
hosted/terminal paths and Clerk subscription billing — never “out of scope”
by assertion. Privacy: tenant isolation, deletion/offboarding, no cross-shop training
without an approved policy. Remaining tax work is vendor sales tax versus
SaaS subscription tax (counsel), not a consumer-marketplace facilitator
analysis. Canadian counsel still reviews SaaS/subscription tax and POS
tax-recording facts before go-live of those features.
