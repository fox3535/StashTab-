# Bounded security-testing model

No scanners, attack tools, payment sandboxes, models, or schedules are
enabled here. This file does **not** start a test window.

## Tiers

| Tier | Cadence | Environment | Box |
|---|---|---|---|
| Passive PR checks | Each same-repo PR | CI | Lint/secrets/pytest; no exploit payloads; no live Stripe/PayPal |
| Weekly testing | Time-boxed | Isolated staging on a **signed allowlist** | Synthetic data only |
| Pre-release | Named SHA | Same allowlist | Authz, cash-session, webhook fixtures, advisory write-blocks |
| Quarterly IR/recovery | Quarter | Isolated restore **after token scrub** | |
| Independent pentest | Annual / major change | Allowlisted staging | Independent human; signed ROE |

Major change examples: first production RLS, first Web Push, first JustTCG
production key, **first POS card capture**, first Portfolio/Market Watch
promotion, authn redesign.

## Tests when later slices unlock (fixtures until sandbox approved)

Payments/POS:

- Header shop-id / Clerk user-id cannot **read or write** another shop’s
  cash session, lots, recs, or paid flag
- Cash/trade vendor confirm finalizes immediately; electronic tender
  **reserves** then deducts only after signed webhook; fail/cancel/expiry
  **releases**
- Duplicate provider event id is a no-op for that shop + **transaction**
- Redirect success does not mark paid or deduct
- Unsigned webhook rejected; duplicate event id is a no-op
- No PAN fields in schema or logs
- No wallet/escrow/payout tables

Portfolio / Market Watch:

- Recommendation insert cannot change inventory qty or list price
- Abstention when identity/variant/condition/freshness/liquidity/agreement
  insufficient
- Cross-shop lot data does not appear in another shop’s analysis
- Point-in-time eval rejects future observations
- Prior recommendations excluded from market observation features
- Duplicate sale ids do not double-count volume

Passive PR checks may fail only for **already approved** rules. Must not fail
because SOC 2, PCI, or Watch programs are unfinished.

Adjudicator: Control owner — Application. CI validates; it is not a second
adjudicator.
