# Tenant lifecycle (planning)

Implementation blocked. This is **SaaS tenant** approval (create/operate a
`shop`), not marketplace seller KYC.

Consumers do not operate StashTab. Withdrawn products (consumer listings,
payouts, meetup) stay withdrawn.

## States

```text
applicant
  -> identity_pending
  -> under_review
  -> approved | rejected

approved
  -> restricted | suspended

restricted | suspended
  -> approved (after human review) | closed
```

An **approved** tenant may use POS, inventory, intake, reporting, and (when
separately unlocked) payment reconciliation, Portfolio Watch, and Market
Watch.

Provider KYC on a Stripe/PayPal **vendor merchant account** is independent.
It does not grant StashTab tenant approval, and StashTab approval does not
grant provider production credentials.

Suspension prevents **new** operational use according to policy without
destroying historical records.

## Who transacts

Only the tenant’s staff (and invited shop members) operate StashTab.
