# Rules of engagement

**This file does not authorize any test.** A test starts only with a signed
record: named human, ISO window, **hostname allowlist artifact**, ticket id.

## Authorization

Same-repo humans only; fork PRs never receive secrets. Targets must appear on
the signed allowlist. Production, Railway prod URLs, production Clerk,
production Stripe/PayPal, production market-data accounts, and production
Postgres are prohibited. Localhost is prohibited unless explicitly listed.
Isolated staging must use distinct hostnames and distinct provider accounts.
Production credentials, including tokens inside a restored database, must not
be used.

## Data

Synthetic shops. If real customer, PAN-like, or another tenant’s acquisition
costs appear, **stop** and `cancelled`.

## Limits (future runner defaults)

Staging API 5 rps / 5 sessions. Clerk / Stripe / PayPal / Shopify / market
APIs out of scope unless that host is on the signed list. Window 120 minutes
weekly; 8 hours pre-release. Redirect follow 0. Concurrent windows: 1 global
lock.

## Kill switch

Named human sets abort. Agents stop **immediately** on next action. Heartbeat
is health only.

## Allowed techniques (closed list)

Read-only recon of allowlisted HTTP API, authenticated test users, fixture
webhook bodies, advisory write-block negatives. **Not** implied: attacking
third-party marketplaces, SSRF against cloud metadata, production stores.

## Prohibited

Ransomware, wipe, DROP DATABASE, persistence leftovers, exfiltration off the
named log store, production stuffing, social engineering, DoS above caps,
mass deletes, custom PAN forms, using findings against unlist hosts, editing
this package during a window to expand targets, training on live customer
data.

## Logging

Append-only: actor, idempotency key, allowlisted host, start/end, technique
category. No secrets, no PAN, no customer PII, no raw acquisition-cost dumps
off-box.
