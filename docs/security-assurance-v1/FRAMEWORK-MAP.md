# Framework mappings (planning)

Interpretive aids only. Not a frozen security contract.

## NIST CSF 2.0

Govern (precedence, adjudicators). Identify (API, Postgres, worker, Clerk,
Shopify, future vendor Stripe/PayPal, market-data sources, cash drawer).
Protect (intended authn/z and `shop_id`; **current** `deps.py` is a verified
gap). Detect (future PR checks, audit logs). Respond (IR exercise, kill
switch). Recover (PITR).

## NIST SSDF

Human-approved phases; implementation blocked until entry gate. Protected
main; no secrets in Git. FastAPI ownership. Independent reviewers; agents
cannot self-waive.

## OWASP ASVS (target L2) and API Security Top 10

| Topic | Current verified gap / fact |
|---|---|
| V2/V3 Authentication | `X-Clerk-User-Id` without Bearer even if issuer set (`clerk.py`) |
| V4 Access control | First membership; unauthenticated `X-Shop-Id`; unauthenticated shop invite |
| V5 Validation | Notification URLs tightened; analytics writes must be shop-scoped |
| API1 BOLA | Every query filters authorized `shop_id` (contract §3.1, §13.7) |
| API2 Auth | Payment webhooks need signatures, not Clerk |
| API3 Property | Acquisition costs and recs must not leak across shops |
| API4 Resource | No application rate limit today |
| API5 Function | Roles unused; cash-close and rec-create need roles |
| API7 SSRF | Push allowlist exists; market-data URLs must be pinned |
| API8 Misconfig | `debug` default true; CORS allow-all; `/docs` on |
| API10 Unsafe use | Shopify, Clerk JWKS, JustTCG; JWT `verify_aud: False` |

## Privacy

Purpose: operate one card business’s POS/inventory/analytics. Not selling
personal data. Isolation: `shop_id`. Retention: provider responses per
contract §9; market-data license TBD. Deletion/DSAR unspecified. Convex and
Clerk hold user records.

## PCI DSS (in analysis)

No PAN/CVV storage intent. Hosted/terminal capture only. Include Clerk
Billing, POS card **label**, Shopify vendor-shop orders. Specialist before
production card capture.

## Analytics / model risk

Separate confidences; abstention; point-in-time eval; no production self-
modification; tenant-isolated learning default (`AI-RISK.md`).
