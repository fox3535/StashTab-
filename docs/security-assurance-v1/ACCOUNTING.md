# Accounting and cash-drawer design (planning)

**Not a general ledger.** Do not call this complete accounting until a
qualified accountant reviews it. Implementation blocked: no new financial
tables or migrations in this package.

Reuse-before-build: extend `Sale`, `PendingTrade`, and `ShowSession`.
Preserve existing show P&L until a later ledger matches it. Do not create a
parallel accounting product.

## Boundary

StashTab helps **one vendor** keep operational books for **that shop**.

- Record the vendor’s gross sale, tax, discounts, tender (cash/trade/card
  label/provider), processor fee if known, refund/dispute adjustments.
- **StashTab subscription fees** are StashTab revenue. Vendor POS gross is
  **not** StashTab revenue.
- Do not design marketplace GMV, platform take-rate, seller net payout, or
  escrow ledgers.
- All records are `shop_id` scoped. FastAPI owns writes.

## Proposed operational subledger

Immutable **ledger entries**. Corrections are **reversing entries**.

Reuse-before-build: extend `Sale`, `PendingTrade`, and `ShowSession` in
place. New financial columns use exact money; **migrate** live float
columns with backfill. Do not create a second money ledger beside `Sale`.
- Types: `cash`, `trade`, `stripe`, `paypal`, `refund`, `chargeback`,
  `adjustment`, `fee`, `subscription_fee` (StashTab SaaS, separate books).
- Identifiers: receipt/transaction, sale **line**, shop, tender, provider
  event ids, cash session, idempotency keys.

COGS method (FIFO / weighted average / specific identification) is a
**deferred accountant gate**. Capture complete lot history anyway (D-008).

Trade-credit vs stored-value treatment is a **deferred** legal/accounting
gate, not a planning-package blocker. Do not add a StashTab wallet.

## Cash drawer / session

```text
expected closing cash =
  opening cash + cash sales - cash refunds + cash added - cash removed

variance = counted cash - expected closing cash
```

Record opening amount, expected vs counted, person opening and closing,
timestamps, denomination counts if enabled, variance explanation, approval,
immutable adjustments.

Trade-credit vs stored-value **booking** is deferred (D-008). Do not design
a StashTab stored-balance product while that gate is open.

## Webhook vs books

Provider events create or reverse entries only after signature verification
and idempotent apply. Unmatched events stay pending-reconciliation, not
silent success.

## Portfolio / Market Watch

Unrealized gain/loss and “estimated market value” are **advisory analytics**,
not booked revenue. Do not post mark-to-market into the cash subledger
without accountant review.
