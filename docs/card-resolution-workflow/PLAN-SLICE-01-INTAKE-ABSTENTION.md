# Planning packet — card-resolution intake/abstention

**Slice:** `card-resolution-core-v1 / slice-01-intake-abstention`
**Status:** `PLANNING APPROVED (D-030); POLICY FROZEN (D-033); LOCAL IMPLEMENTATION ACCEPTED (D-034) — NOT MERGED, NOT DEPLOYED, FEATURE OFF`
**Pinned `main`:** `d49eca9fc31298847bd07abf42347ab691b4f974`
**Frozen contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0
**Amendments:** 1.1.0 proposed (notifications, delivery off); 1.1.1 and 1.1.2 frozen for notification backend only
**This file is not in freeze hashes.** Do not edit the frozen contract.

This planning packet is historical. Local implementation was later accepted
as D-034: not merged, not deployed, feature off. Do not enable staging
or production from this file.

## 1. Why this slice

D-029 accepted empty-table inventory search. Inventory writes stay off.
Inventory-truth staging proof still needs a later write unlock. Notification
backend 1.1.2 is accepted on `main` and not deployed.

The F0 exit gate still needs a bounded card-resolution intake path that can
**accept, abstain, or reject** without paid lookup. This slice is that path.

## 2. Existing-behavior map

| Partner | Current StashTab | Preserve | Contract conflict | Missing test |
|---|---|---|---|---|
| `vendor/mimir-partner/core.py` `process_card` | none | Ordered extract → lookup → hold | Single-shop; no `shop_id`; `needs_review` if OCR name confidence `< 70` but still builds a staging payload; weak OCR can continue | Shop-scoped intake; abstain on weak evidence; no silent continue |
| `vendor/mimir-partner/core.py` `PokemonTCGAPIClient.fetch_card_data` | `services/api/app/logic/pokemon_api.py` `PokemonAPI.fetch_card_data` | Set + number lookup; official name/image | Fuzzy name `WRatio >= 80` sets `match_verified`; promo fallback can return a “best” card with no floor; not JustTCG; not versioned component scores | Unique ≥0.95 local accept without network; ambiguous must not auto-accept |
| `vendor/mimir-partner/api_client.py` `PokemonAPI` | same lookup helper | Official set/number fields | Network identity is treated as verification | No-network fail-closed test |
| `vendor/mimir-partner/logic.py` `add_to_staging` / `CoreManager.add_to_staging` | `logic/intake.py` `add_to_staging` via `POST /admin/intake/staging` | Shop-scoped hold row; merge same identity | Writes `staging_item` (not on staging Neon); `needs_review=True` for singles but still inserts; commit path writes inventory | No inventory/staging write from resolution |
| `vendor/mimir-partner/ocr_engine.py` | unused in API | Future evidence fields | Out of slice | Not this slice |
| none | `POST /admin/intake/lookup` | Set/number query shape | **Unauthenticated**; no `shop_id`; calls Pokemon TCG API; 404 if empty | Auth + membership; no provider call |
| none | `POST /admin/intake/staging` then `/admin/staging/{id}/commit` | Shop context on write | Commit writes `inventory_item` + truth receive; gated by cutover, not by card-resolution accept | Resolution must not reach those tables |
| none | `InventoryItem.needs_review` / `StagingItem.needs_review` | Boolean flag exists | Flag is not a review queue, not durable resolution state, not contract terminals | Durable shop-scoped review rows with reason codes |
| none | card-resolution module / JustTCG client / review queue | — | Missing | Entire slice |

Do not call or extend `/admin/intake/lookup` or `/admin/intake/staging` here.

## 3. Outcome model

One request reaches exactly one explicit result:

| Result | Meaning in this slice | Contract mapping |
|---|---|---|
| `accepted` | Identity accepted locally. **Not** inventory. | Terminal `accepted` for identity only; must **not** reach §10 inventory commit |
| `abstained` | Human review. Durable queue row. | `pending_human_review` |
| `rejected` | Invalid or unsupported. | Terminal `rejected` |

`unchanged/merged` is out of slice (no inventory row to merge).

JustTCG stays **disabled** (budget = 0 / feature off). Contract §5 says
ambiguous (`0.70–0.9499`) may attempt JustTCG if budget allows. With lookup
off, those cases **abstain**. That is stricter, not weaker. Emergency disable
of lookup is already allowed (§15).

### Future JustTCG (specify only; do not call)

A later unlock may call JustTCG only when **all** are true:

- this slice would otherwise abstain for ambiguity (`0.70–0.9499`) or need
  stable-id validation/enrichment;
- no conflicting stable identifiers;
- no fresh cache hit;
- tenant/job/global budget remains;
- JustTCG feature flag on;
- not used to settle identifier conflicts or because an agent is unsure.

Timeout, empty result, conflict, or budget exhaustion → still abstain or
reject. Never auto-accept.

## 4. API contract (specified; not implemented)

Authorization: verified Clerk JWT + shop membership. `X-Shop-Id` is a hint
only (`get_shop_context`). No header-only user. No unauthenticated lookup.

**`POST {api_prefix}/card-resolution/intake`**

Input:

- `intake_id` (client idempotency key, required)
- evidence: `game`, `name`, `set_name` and/or `set_code`, `collector_number`,
  optional `language`, `printing`, `edition`, `variant`, optional stable ids
- optional `candidates[]` for tests/fixtures only (each must carry `shop_id`
  equal to the verified shop or be rejected)
- optional `correlation_id`

This slice does **not** accept image blobs or OCR. Missing game **and** name
**and** set+number → `rejected` (`unsupported_or_incomplete_evidence`).

Output (always JSON, never inventory):

- `shop_id`, `intake_id`, `correlation_id`
- `result`: `accepted` \| `abstained` \| `rejected`
- `state` (workflow value below)
- `reason_codes[]`
- `identity_confidence` (0.00–1.00) and `price_confidence` (null in this slice)
- `confidence_components` (named parts)
- `ruleset_version` (scoring) and `contract_version` (`1.0.0`)
- ranked `candidates[]` with scores (may be empty)
- `justtcg_invoked`: always `false`
- `review_id` when abstained
- `evidence_refs[]` (hashes/ids of stored evidence, not raw provider blobs)

**`GET {api_prefix}/card-resolution/reviews`** — list open review rows for the
verified shop only.

**`POST {api_prefix}/card-resolution/reviews/{review_id}/decide`** — human
`accept_identity` / `reject` / `defer`. Accepts identity only. **No inventory
write.** Actor Clerk id audited.

Replay `POST /intake` with same `shop_id` + `intake_id` returns the stored
outcome without a second decision.

## 5. Data ownership and proposed schema

New objects are **resolution-owned**, not inventory. Migrator-owned tables.
API may INSERT/UPDATE these tables only after a named implementation unlock.
API still has **SELECT-only** on D-028 inventory tables.

Proposed tables (local PostgreSQL 16 first; **not** staging Neon in this
planning packet):

1. `card_resolution_intake` — one row per `(shop_id, intake_id)`; evidence
   snapshot; state; result; confidences; ruleset/contract versions;
   correlation_id; result hash.
2. `card_resolution_candidate` — ranked local candidates for that intake.
3. `card_resolution_review` — durable queue; shop-scoped; reason codes;
   status open/decided; assignee optional.
4. `card_resolution_audit` — append-only decisions and human actions.

Unique `(shop_id, intake_id)`. All FKs include `shop_id`. No FK from these
tables into `inventory_item` in this slice.

First apply target: disposable local Postgres (same pattern as inventory
schema rehearsal). Staging Neon apply is a **later named unlock**.

## 6. Authorization and isolation

- JWT + membership required on every route.
- Shop from verified membership, not from body `shop_id`.
- Body `shop_id`, if sent, must match verified shop or 403.
- Candidates naming another shop → `rejected` or `abstained`, never accepted.
- Review GET/decide scoped to verified shop; cross-shop id → 404.
- JustTCG key unused; must not appear in logs or fixtures.

## 7. State machine (this slice)

```text
received
  -> normalized
  -> local_matched
       -> accepted                 (identity only)
       -> abstained / human_review_pending
       -> rejected
```

Never entered here: `external_validation_pending`, `pricing_verified`,
`staging_ready`, `inventory_committed`.

### Deterministic vs advisory

| Actor | May |
|---|---|
| Versioned scorer | Compute components, choose accept/abstain/reject |
| Advisory agent | Attach a **non-authoritative** note; never set `accepted` |
| Human reviewer | `accept_identity` or `reject` after seeing evidence |
| Timeout / missing data / model failure | `abstained` or retryable failure, **never** `accepted` |

## 8. Scoring (proposal; not frozen)

See `docs/card-resolution-workflow/SCORING-POLICY-INTAKE-ABSTENTION.md`.
Identity-only exact-match sum. Price and fuzzy name must not raise `S`.
RapidFuzz ≥80 is not verification (D-031). JustTCG stays off. Owner still
chooses margin 0.05 / 0.10 / 0.15. Do not treat 0.05 as the default.

## 9. Idempotency and concurrency

- Client `intake_id` + `shop_id` is the idempotency key.
- Insert intake row first. Unique violation → return existing result.
- Concurrent first writes: one commit wins; the other reads the winner.
- Human decide is idempotent on `(review_id, shop_id)` once decided.
- No second scorer run after a stored terminal result.

## 10. Human review

Abstain creates `card_resolution_review` in the same transaction as the
intake result. Queue is shop-scoped. List/decide require membership.

Human `accept_identity` sets intake to `accepted` (identity) with
`decision_source=human`. Still **no** inventory, lot, event, price, sale,
purchase, notification, Shopify, payment, or Watch write.

Defer leaves `abstained`. Reject is terminal `rejected`.

## 11. Retry and terminal failure

- Replay identical request: same stored result.
- Scorer exception, timeout, or missing catalog: `abstained` with
  `reason_codes` including `scorer_failure` or `insufficient_evidence`.
  Not success.
- No automatic retry loop in this slice.
- Provider HTTP is forbidden; any attempted network identity call is a
  failed test.

## 12. Audit

Each outcome stores contract §9 logical fields. `justTcg*` empty.
`decisionSource` is `rules_local` or `human`. `priceConfidence` null.
Evidence is the normalized snapshot + candidate list hash, not Pokemon or
JustTCG payloads.

Reconciliation for a batch (even a single request):

```text
source_count = accepted + abstained + rejected
unaccounted_count = 0
```

JustTCG request count must be 0.

## 13. Rollback

- Planning/docs only until implementation unlock.
- After local implementation: drop new resolution tables in local PG; do not
  drop D-028 inventory/identity.
- Staging Neon is untouched by this slice.
- Feature flag default off. Disable auto-accept without a contract change (§15).

## 14. Acceptance tests (when implementation is unlocked)

Must prove, locally:

1. Unique local candidate `>= 0.95` → `accepted`; JustTCG not called.
2. Two plausible candidates → `abstained`; review row created.
3. Score `< 0.70` → `abstained` or `rejected` per rule; never inventory.
4. Identifier conflict → `abstained`; never accepted.
5. No JWT / spoofed shop → 401 / 403.
6. Other shop’s `intake_id` or review id → 404.
7. Replay same `intake_id` → same result, one intake row.
8. Parallel same key → one winner, identical body.
9. Advisory note cannot flip result to `accepted`.
10. Scorer exception → not `accepted`.
11. No writes to `inventory_item`, truth tables, `sale`, `purchase_record`,
    `staging_item`, notification, Shopify, payment, Watch tables.
12. `justtcg_invoked` is false; no Pokemon TCG HTTP.
13. Identity confidence ≠ price confidence (price remains null).
14. Unaccounted count is 0.

Contract §13.2–3, 11, 14 (JustTCG cache/spend, inventory outbox, labeled
false-accept eval) stay **out of this slice** and are listed as remaining
gates.

## 15. Explicit exclusions

OCR/images; CSV import identity; JustTCG client; Pokemon TCG API;
`/admin/intake/*`; inventory/lot/event/price/sale/purchase writes;
notification send (amendment 1.1.0 unused); Shopify; payments; Watch;
staging Neon DDL; production; frontend review UI polish; changing frozen
thresholds.

## 16. Contract amendment

**Not required before implementation** if JustTCG stays disabled and
ambiguous/weak cases abstain. That uses §5 + §15 (lookup off / budget 0).

Do **not** freeze amendment 1.1.0 for this slice (notifications).

An amendment is required only if the owner later wants auto-accept in the
ambiguous band without JustTCG, different thresholds, or agents auto-accepting.

## 17. Owner decisions

Scoring policy is owner-recorded as D-032 (margin 0.10, weights, Pokémon
registry, no silent game default, omitted printing abstains, printing
ineligibility only via `printing-map-v0`). See
`SCORING-POLICY-INTAKE-ABSTENTION.md`. **Not contract-frozen until vote.**

### Remaining before implementation (not scoring)

1. Named implementation unlock.
2. Tests-only vs HTTP in the first code slice.
3. Who may `decide` on review rows (owner vs any member).
4. First schema apply remains local Postgres, not staging Neon (D-030).

### Deferred to JustTCG activation or production

- Budgets, cache freshness, labeled-set size, false-accept pause limit.
- Provider ids on inventory vs catalog tables.
- Raw provider retention.
- Review UI.
- Amendment 1.1.0 notification freeze.
- Inventory promotion after identity accept.

## 18. Terminal recommendation

Scoring decisions are closed. Proposed freeze packet:
`freezes/PROPOSED-IDENTITY-SCORE-v0.md`. Wait for owner freeze vote.
Do not apply freeze hashes or write code in this action.

Contract §13 JustTCG/inventory items remain later gates.
