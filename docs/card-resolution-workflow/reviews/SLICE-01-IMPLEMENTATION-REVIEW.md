# Bounded review — local intake/abstention implementation

**Slice:** `card-resolution-core-v1 / intake-abstention-local-v0`
**Freeze checkpoint:** `671f663`
**Implementation:** merged on `main` `6a266b1` via PR #13 (D-034); not deployed, feature off
**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0
**Policy:** `identity-score-v0`

One review round. Findings below. No second review loop.

## Architecture

Separate metadata owns the six resolution tables. Application startup create-all does not create them. The HTTP router is mounted always; the gate is fail-closed unless env is local/test and the flag is on. Scoring is a pure function. JustTCG/TCGCSV/Pokémon TCG HTTP are not called. Accepted identity does not write inventory.

**Open:** none blocking. Staging enablement remains a later named unlock.

## Data integrity

Unique `(shop_id, intake_id)`. Replay with the same evidence hash returns the stored row. A different payload on the same key is 409. Abstention writes one review row in the same transaction. Evidence and audit are insert-only with update/delete triggers.

**Open:** none blocking.

## Database security

PostgreSQL apply uses the migrator role. API gets SELECT plus the DML needed for intake/review. Catalog is SELECT-only for API. Worker and readonly get nothing. PUBLIC has no table rights. Rollback drops only the six resolution tables and leaves identity and live inventory parents.

**Open:** this apply is local disposable Postgres only. Staging Neon is untouched.

## Application security

Routes use verified bearer identity plus shop membership. Shop header is a hint. No token and spoofed headers fail. Cross-shop review ids 404. Owner and staff of the same shop may decide. Human accept still writes no inventory.

**Open:** none blocking for this slice.

## Adversarial / concurrency

A process lock plus unique constraint handles concurrent identical keys. Fuzzy name retrieve cannot accept. Price and model-confidence fields cannot raise the identity score. Other-shop candidates reject.

**Correction applied:** HTTP exceptions from the gate are not converted into an abstention.

## AI evaluation

No model score enters `S`. Advisory notes are ignored. There is no LLM path on this endpoint.

## Workflow liveness

Missing/unsupported/mismatched game rejects. Omitted language/printing, duplicates, conflicts, empty catalog, scorer failure, and timeout abstain and create a review row. Human accept/reject/defer is durable. Replay does not score again.

**Open:** frontend review UI, JustTCG, and inventory promotion remain later gates.
