# Directive — slice-01 local intake/abstention

**Status:** `MERGED ON main 6a266b1 — NOT DEPLOYED — FEATURE OFF`
**Frozen policy:** `identity-score-v0`
**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0
**Unlock `intake-abstention-local-v0` was given. Implementation is accepted as D-034 and merged via PR #13. It is not deployed, and the feature stays off.**

The executed local slice is:

1. Authenticated, shop-scoped intake endpoint in FastAPI (JWT + membership;
   `X-Shop-Id` is a hint only).
2. Apply `identity-score-v0` only. Integer hundredths. Auto-accept only at
   100 with six exact fields, one eligible identity, margin ≥ 10.
3. Outcomes: accept (identity only), abstain (durable shop-scoped review
   row), or reject. No inventory, lot, event, price, sale, purchase,
   Shopify, payment, Watch, or notification writes.
4. JustTCG and TCGCSV remain off. No provider HTTP. RapidFuzz retrieve
   only, never verify.
5. Tests against **disposable local PostgreSQL** only. No staging Neon
   DDL. Replay same `intake_id` is idempotent.

Do not merge, deploy, migrate staging/production, or enable the flag
without a later named unlock.
