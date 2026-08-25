# SOC 2 Type I — roles, ownership, and evidence sketch

Planning only. No auditor engagement.

## Trust services in first scope

Security (required). Availability and confidentiality as backups/PITR and
tenant isolation are evidenced. Processing integrity for card-resolution
(frozen contract §11) and cash/payment reconciliation. Privacy for shop
staff PII and acquisition-cost confidentiality. PCI analyzed in `PAYMENTS.md`
and **not** declared out of scope.

Add unnamed-until-enablement owners: **Payments** (vendor merchant webhooks),
**Accounting** (subledger exports), **Analytics** (Portfolio/Market Watch
promotion). Five engineering roles collapsing onto one person is a Type I
gap, not a blocker for card-resolution.

## Accountable roles

One human adjudicator per gate. Agents cannot attest.

Until names are recorded, placeholder is “named human required.”

## Control families (examples)

Governance, communication, risk (tenant isolation, secret exposure, market
manipulation of advisory data), monitoring, control activities (authz,
`shop_id`, advisory write-blocks), logical access, operations, change,
vendor inventory (Clerk, Shopify, future Stripe/PayPal, market-data
licenses), availability (PITR), confidentiality (no PAN; lock-screen when
notifications ship), privacy (offboarding; no cross-shop training default),
processing integrity (idempotent webhooks; point-in-time evals).

## What this package does not do

It does not create a blocking SOC 2 gate on card-resolution-core-v1.
