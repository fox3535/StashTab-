# POS and payment-state machine (planning)

Implementation blocked for **new** payment capture, reservation events, and
cash-session fields. Existing mobile POS checkout is **already implemented**
(cash, trade, card-as-label). This file is the later overlay, not a
replacement POS (D-007, D-008).

## Receipt (approved product)

One customer checkout is **one transaction/receipt** with one or more
existing `Sale` **lines**. Add a compatible parent receipt identity
(`shop_id` + receipt/transaction id). Do not replace `Sale` rows.

Provider idempotency (when a charge exists): `shop_id + transaction_id`
(stable; no `attempt` in the provider key). Lines share that parent.

## Existing cash / trade (preserve)

Vendor-confirmed cash and trade may **finalize immediately**: write the
receipt + lines and deduct inventory in the same confirmation, as today.

## Later electronic tender (blocked until payments slice)

Today’s `card` **label** is not this path and is not provider-paid.

```text
electronic_checkout_started
  -> inventory reserved
  -> provider_session_created
       -> webhook_verified_paid
            -> sale_finalized (receipt + lines; inventory deducted)
       -> failed | cancelled | expired
            -> reservation released
```

Browser success URL is **not** `webhook_verified_paid`. Deduct and
Shopify-commit only after the signed, idempotent webhook.

## Cash session (blocked; extend show/POS close)

```text
session_open
  -> session_counted
  -> variance_explained | variance_approved
  -> session_closed
```

Closed sessions are immutable except reversing adjustments.

## Capability

Restricted/suspended tenants cannot open new sales. No consumer marketplace
or meetup payment path.
