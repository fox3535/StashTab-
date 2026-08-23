# Payments, PCI, and funds-flow (planning)

**Implementation blocked.** Do not integrate Stripe or PayPal, store production
credentials, create payment tables, or claim PCI/SOC 2 readiness.

## Intended product model

Each approved tenant transacts **only with its own customers through its own
POS**. There is no StashTab consumer checkout.

### Cash (primary in-person path)

StashTab must record cash sales and support audited end-of-day cash-drawer
reconciliation. See `ACCOUNTING.md`.

### Stripe / PayPal (optional later)

If integrated, they connect to **that vendor’s own merchant account**. The
vendor remains merchant of record and owns pricing, taxes, refunds, disputes,
chargebacks, and customer fulfillment.

Use provider-hosted fields, approved SDKs, or certified terminals. StashTab
must not collect or store PAN or CVV.

Verified today: POS records cash/trade and a card **settlement label**. That
label is not a PCI-complete integration.

### StashTab subscription billing

Clerk Billing (SaaS tiers) is a **separate transaction domain** from vendor
POS payments. Do not mix subscription revenue with vendor sale proceeds in
reporting.

## Funds custody

StashTab must **not** hold, pool, distribute, delay, or release vendor funds.
No StashTab wallet, stored balance, escrow, payout engine, or release button.

Provider settlement, reserves, KYC holds, and fraud holds remain
provider-controlled and must be shown as such.

## Refunds, disputes, taxes

The vendor funds and decides refunds on its merchant account. StashTab may
record provider status and support bookkeeping. Do not assume StashTab funds
refunds.

Taxes: the vendor calculates, collects, reports, and remits for **its**
sales. Remaining tax work is **vendor sales tax versus StashTab SaaS
subscription tax**. Do not treat “no consumer marketplace” as a finished
marketplace-facilitator legal opinion. Canadian counsel still reviews SaaS
tax and POS tax-recording facts before those features go live.

## Webhooks and proof of payment

If POS electronic payments are unlocked later: signature-verified,
idempotent, FastAPI-side webhooks; reconcile to the **vendor** merchant
account. Browser redirect is not proof of payment. Shop identity for a
webhook comes from the signed provider account mapping, not `X-Shop-Id`.

Fail-closed identity is an entry gate for any payments slice.

## PCI (in analysis — not out of scope)

- No PAN/CVV/track/raw credentials in StashTab.
- May store provider identifiers.
- Include Clerk Billing, POS card label, and Shopify-synced **vendor shop**
  orders in CDE discussion.
- SAQ/QSA and provider confirmation are **deferred professional gates**
  before **production** card capture. They do not block planning this
  reservation/webhook state machine.

## Deferred professional gates (not planning blockers)

Recorded in D-008. Planner/reviewers choose schema, indexes, backfill,
events, idempotency, and tests from repository evidence.

- Final COGS/accounting method
- Trade credit and stored-value accounting treatment
- Market-data licensing
- PCI determination
- Stripe/PayPal **production** configuration
- Production migration approval

Still require a named `implementation_unlock` before any payments code.
Default: StashTab staff must not fire refunds on vendor merchant
credentials until terms and a role gate exist. No custom PAN form.
