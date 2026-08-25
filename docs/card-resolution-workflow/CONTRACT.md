# StashTab Card Resolution and Pricing Workflow Contract

**Contract ID:** `STASHTAB-CARD-RESOLUTION-001`  
**Version:** `1.0.0`  
**Status:** `FROZEN`  
**Frozen on:** `2026-08-14`  
**Applies to:** card intake, OCR-assisted intake, catalog matching, pricing enrichment, staging, and promotion to inventory  
**System of record:** this versioned file in the StashTab Git repository

## 1. Purpose

This contract defines how StashTab resolves a physical or imported card to a canonical catalog record, when it may spend JustTCG API credits, when human review is required, and what evidence must exist before a card can be promoted to inventory.

The controlling hierarchy is:

```text
Local matching -> JustTCG validation -> Human review -> Verified database write
```

AI agreement is not proof of correctness. Agents may interpret evidence and propose candidates, but database writes are authorized only by deterministic rules, validation, and the gates in this contract.

## 2. Scope

### In scope

- Manual card intake
- CSV and catalog imports
- Future OCR/image-assisted intake
- Local catalog candidate selection
- JustTCG card and variant lookup
- Human resolution of ambiguous cards
- Pricing enrichment after identity resolution
- Staging and promotion to inventory
- Audit, reconciliation, retry, and API-credit controls

### Out of scope

- Replacing existing Python business logic with TypeScript
- Autonomous production migrations
- Treating JustTCG as an image-recognition service
- Allowing an AI model to approve its own uncertain match
- Using card names as canonical database identifiers
- Determining physical card condition solely from catalog pricing data

## 3. Non-negotiable invariants

1. Every tenant-owned record and query is scoped by `shop_id`.
2. An unresolved or ambiguous card never enters sellable inventory.
3. Card identity confidence and price confidence are stored and evaluated separately.
4. A JustTCG response cannot repair missing physical evidence by itself; it can validate or enrich a candidate.
5. Conflicting stable identifiers always require human review.
6. Every accepted match retains its evidence, source, rule version, and timestamps.
7. Every intake record reaches exactly one accounted-for terminal result: accepted, unchanged/merged, rejected, or pending human review.
8. Retrying the same intake event is idempotent and cannot duplicate inventory.
9. API secrets remain server-side. `JUSTTCG_API_KEY` must never be exposed to the browser or committed to Git.
10. External provider failure never causes an uncertain card to be silently accepted.

## 4. Canonical identity

### Preferred identifiers

Use stable identifiers in this order when available:

1. Existing StashTab canonical card/variant identifier
2. JustTCG card UUID and variant UUID
3. TCGplayer product ID and SKU/variant ID
4. Game-specific stable identifiers such as Scryfall or MTGJSON IDs
5. A normalized composite key only when no stable provider identifier exists

The normalized composite key must include enough fields to distinguish printings:

```text
game + set + collector_number + language + printing/finish + edition + variant
```

Card name alone is never a valid unique key.

### Evidence fields

Candidate scoring may use:

- Game
- Card name
- Set name or set code
- Collector/sequence number
- Language
- Printing, finish, or foil treatment
- Edition or release
- Rarity
- Stable provider identifiers
- OCR token confidence and image region provenance

Condition is recorded independently from catalog identity. An external variant price may be selected only after the condition and printing required by that variant are known.

## 5. Confidence model

Confidence is a deterministic score from `0.00` to `1.00` produced by a versioned scoring function. The implementation must record the component scores and scoring-rule version; it must not store only a model's narrative judgment.

### Initial thresholds

| Identity result | Score/rule | Required action |
|---|---:|---|
| Exact local match | `>= 0.95`, unique candidate, no conflicts | Accept identity locally |
| Ambiguous local match | `0.70-0.9499`, or multiple plausible candidates | Attempt JustTCG validation if budget permits |
| Weak local match | `< 0.70` | Human review; JustTCG may retrieve candidates but cannot auto-accept without exact corroboration |
| Identifier conflict | Any score | Human review |
| No candidate | N/A | Human review or explicit rejection |

An auto-accepted result must also satisfy all of the following:

- The highest-scoring candidate is unique.
- The margin over the second candidate meets the configured minimum.
- Game, set, and collector number do not conflict.
- Printing, language, and edition are resolved when relevant.
- No required identity field is inferred solely from price similarity.

Thresholds are starting policy, not empirical truth. They may change only through the contract amendment process after evaluation against a labeled card set.

## 6. JustTCG fallback policy

### Permitted triggers

A JustTCG request is permitted when at least one is true:

- Local confidence is within the ambiguous band.
- A stable identifier exists and needs validation or enrichment.
- Local catalog data is stale or missing required price data.
- Multiple local candidates can be distinguished using provider metadata.
- A resolved identity needs its condition/printing-specific price refreshed.

### Prohibited triggers

Do not spend credits merely because:

- An agent reports that it is "not comfortable."
- The same unresolved evidence has already produced the same provider result.
- A cached response is still within the configured freshness window.
- The request would exceed tenant, job, or global budget.
- The only purpose is to obtain another opinion after an identifier conflict.

### Request strategy

- Prefer direct lookup by stable identifier over free-text search.
- Cache by provider, endpoint version, stable identifier, variant, and relevant query fields.
- Batch eligible lookups within the provider plan's current limits.
- Apply bounded retries with exponential backoff and jitter to retryable failures.
- Do not retry authentication, malformed-request, or exhausted-budget failures automatically.
- Record request count, cache hit/miss, response status, latency, and provider metadata.
- Configure per-job, per-shop, and global daily request budgets outside source code.

### JustTCG outcomes

| Outcome | Action |
|---|---|
| Exact stable-ID match with consistent physical evidence | Upgrade identity evidence and continue |
| Unique metadata match that brings confidence to the auto-accept threshold | Continue, retaining local and provider evidence |
| Multiple results, partial match, or conflicting metadata | Human review |
| No result | Human review or explicit rejection |
| Timeout, rate limit, exhausted credits, or provider outage | Keep pending and retry according to policy; never auto-accept |

## 7. Human review gate

Human review is mandatory for:

- Conflicting stable identifiers
- Multiple plausible printings or variants
- Unresolved language, edition, or finish
- Condition-dependent pricing without a confirmed condition
- Low-confidence OCR evidence
- Provider disagreement
- Suspected counterfeit, altered, or unrecognized cards
- Any case where required evidence is absent

The review UI must display:

- Original input/image and extracted fields
- Ranked candidates with field-level differences
- Local confidence components
- JustTCG evidence and timestamp, if queried
- API fallback reason
- Proposed canonical identity and variant
- Accept, correct, defer, and reject actions

The reviewer identity, decision, timestamp, and any correction must be audited. Corrections should feed a labeled evaluation dataset but must not automatically retrain or change thresholds.

## 8. Workflow states

Each intake item must have an explicit state:

```text
received
  -> normalized
  -> local_matched
  -> external_validation_pending (optional)
  -> human_review_pending (optional)
  -> identity_verified
  -> pricing_verified
  -> staging_ready
  -> inventory_committed
```

Terminal alternatives are:

```text
rejected
cancelled
```

Failures remain in a retryable or reviewable state. They must not be represented as successful inventory commits.

## 9. Required audit record

At minimum, retain the following logical fields. Exact table and column names are an implementation decision.

```json
{
  "shopId": "tenant-id",
  "intakeId": "idempotency-id",
  "localCandidateId": "candidate-id",
  "localIdentityConfidence": 0.82,
  "confidenceRuleVersion": "1.0.0",
  "fallbackReason": "ambiguous_printing",
  "justTcgCardUuid": "provider-card-uuid",
  "justTcgVariantUuid": "provider-variant-uuid",
  "matchedOn": ["tcgplayerId", "set", "collectorNumber"],
  "finalIdentityConfidence": 0.99,
  "priceConfidence": 0.97,
  "decision": "accepted",
  "decisionSource": "rules_with_justtcg_evidence",
  "sourceObservedAt": "timestamp",
  "verifiedAt": "timestamp"
}
```

Raw provider responses may be retained only according to licensing, privacy, and retention policy. Store a normalized evidence record and response hash when raw retention is not permitted.

## 10. Verified database write

Only the FastAPI/Python business layer may promote a verified item to PostgreSQL inventory. The UI and AI agents may propose or approve workflow actions through authorized endpoints, but they do not write inventory rows directly.

Before commit:

- `shop_id` is present and authorized.
- Intake idempotency key has not already been committed.
- Canonical identity and variant are resolved.
- Required condition and pricing fields are resolved or explicitly marked unavailable under an approved rule.
- Unique and foreign-key constraints pass.
- The staging record and audit evidence exist.

The inventory commit and its audit/outbox changes must be transactional. A partial commit is a failure.

## 11. Reconciliation

Every ingestion job must satisfy:

```text
source_count = inserted + updated_or_merged + unchanged + rejected + pending_review
unaccounted_count = 0
```

The job report must include:

- Source count
- Locally accepted count
- JustTCG request and cache-hit counts
- Externally validated count
- Human-review pending count
- Inserted, updated/merged, unchanged, and rejected counts
- Duplicate attempts prevented
- Failed and retryable counts
- Unaccounted count

Post-commit checks must verify tenant scoping, identifier uniqueness, expected inventory deltas, and audit linkage. Alerts are required when `unaccounted_count != 0`, duplicate prevention fails, or error/budget thresholds are exceeded.

## 12. Agent delivery workflow

Agents work against this exact frozen contract version.

1. **Planner:** maps required code and migrations without implementing.
2. **Architecture reviewer:** checks boundaries, multi-tenancy, transactions, and failure states.
3. **Data-integrity reviewer:** checks identifiers, constraints, idempotency, and reconciliation.
4. **Security reviewer:** checks authorization, secret handling, abuse, and external-data risks.
5. **Adversarial reviewer:** attempts to find ambiguous cards and failure paths that would be incorrectly accepted.
6. **Implementers:** work only on assigned, separable components.
7. **Independent reviewers:** inspect the contract, diff, and test evidence without relying on implementer reasoning.
8. **Release gate:** human approval is required for schema migrations, production credentials, and production writes.

Cross-platform AI reviews should receive the same frozen contract and repository commit independently. A synthesis record must resolve disagreements using evidence. Model consensus does not waive any acceptance test.

## 13. Acceptance gates

Implementation is not complete until automated tests prove:

1. A unique `>= 0.95` local match is accepted without an external request.
2. An ambiguous match uses a cached JustTCG result before spending a request.
3. An eligible ambiguous match performs at most the configured bounded lookup.
4. Conflicting stable identifiers always enter human review.
5. A provider outage or exhausted budget never promotes an uncertain card.
6. Replaying the same intake idempotency key does not duplicate inventory.
7. Two shops can ingest similar cards without cross-tenant reads or writes.
8. Identity confidence cannot be substituted for price confidence.
9. Condition or printing ambiguity cannot select a variant price automatically.
10. Every terminal result is included in reconciliation and unaccounted count is zero.
11. Inventory, audit, and outbox writes succeed or roll back together.
12. API keys are absent from client bundles, logs, fixtures, and committed files.
13. Human corrections are audited and preserved as evaluation examples.
14. Threshold behavior is evaluated against a labeled dataset containing visually and textually similar printings.

## 14. Observability and operating limits

Track by shop and globally:

- Local auto-accept rate
- JustTCG fallback and cache-hit rates
- Requests and estimated credits consumed
- Human-review rate and age
- Human overturn rate by confidence band
- False-accept rate from labeled audits
- Provider error and latency rates
- Duplicate prevention events
- Reconciliation failures

Pause automatic acceptance when the measured false-accept rate exceeds the configured safety limit or when a scoring-rule deployment has not passed its evaluation gate.

## 15. Freeze and change control

This contract is frozen at version `1.0.0`. Implementation may add detail but may not weaken its invariants.

A material change requires:

1. A written amendment describing the reason and affected risks.
2. Independent architecture and data-integrity review.
3. Updated acceptance tests and labeled-set evaluation where confidence behavior changes.
4. Human approval.
5. A semantic version update and new Git commit.

Emergency disabling of external lookup or automatic acceptance is permitted as a safety action. Re-enabling requires verification and an audit entry.

## 16. Deferred implementation decisions

The following must be resolved during planning without changing this contract's guarantees:

- Exact scoring weights and minimum candidate-margin rule
- Cache freshness by metadata and price data type
- Per-plan and per-shop JustTCG budgets
- Review queue schema and UI route
- Raw provider-response retention policy
- Labeled evaluation dataset size and acceptable false-accept limit
- Whether provider IDs live directly on inventory records or in normalized catalog tables

