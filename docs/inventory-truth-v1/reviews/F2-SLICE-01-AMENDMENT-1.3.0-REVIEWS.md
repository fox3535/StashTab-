# F2 slice-01 — bounded reviews of proposed AMENDMENT-1.3.0

**Packet:** `STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.3.0`
(`PROPOSED — NOT APPROVED — NOT FROZEN`)
**Inputs:** restored `docs/frontend-recovery-v1/PLAN-F2-SLICE-01-
CONTROLLED-RECEIVE.md`; frozen v1.2.0 CONTRACT/DESIGN/MIGRATION/TESTS
+ `freezes/FREEZE-1.2.0.json` + AMENDMENT-1.1.0/1.2.0; accepted
receive-foundation implementation (`services/api/app/inventory_truth/
core.py`, `core_adjust.py`, `feature_readiness.py`, migrators) and its
PostgreSQL evidence (`tests/test_pg_acceptance.py`, slice-01 acceptance
14/14 ×2 fresh DBs).
**One bounded pass; one correction pass. No frozen file edited.**

## 1. Findings and correction mapping

### P0 findings
None.

### P1 findings

| # | Area | Finding | Correction |
| --- | --- | --- | --- |
| P1-1 | Concurrency | Amendment §6 described the concurrent loser as "treated as retry → reload winner → no_op" without stating that the loser's ENTIRE uncommitted transaction — including its `inventory_item` insert or stock bump — rolls back first. Read alone, the wording could be implemented as an in-transaction reload. | Amendment §6 corrected pass 1: the loser's transaction rolls back wholly (commit-at-end design), then the request re-resolves by client key and returns `no_op`. Directive §4 binds the same wording. |
| P1-2 | Application security | Amendment §5 stated authorization but was silent on the dev bypass that `get_shop_context` can honor when explicitly allowed. | Amendment §5 corrected pass 1: dev bypass MUST be off in staging (fail-closed identity, D-025); directive §3 repeats it. |

### P2 observations (accepted, no change)

- **Duplicate-`(shop_id, sku)` race:** concurrent first receives with
  DIFFERENT client keys can each insert an item row (no unique
  `(shop_id, sku)` exists in the frozen live schema). This is exact
  parity with the accepted trade-apply path (`logic/trades.py`), is
  documented in directive §4, and requires no schema change.
- **Cutover row has no actor column:** operator evidence is recorded in
  the acceptance document; amendment §9 already states this honestly.
- **`_normalize_privileges` currently grants tables only:** sequence
  USAGE grants are new migrator code, inside the provisioning unlock.

## 2. Architecture and scope

Additive-only: one nullable live column, one partial unique, one grant
envelope, one thin endpoint reusing frozen `record_purchase_receive`
and the accepted new-item branch. No parallel system, no truth-table
shape change. Matches AMENDMENT-1.2.0 decision 2 ("New items require a
later receive/lot path") — this is that path, lot-required,
receive-first. Scope excludes everything named in directive §5.

## 3. Data integrity and atomicity

One commit at the end of the transaction covers snapshot, purchase row,
lot, and event; `_write_pair` savepoint isolates pair-only unique
collisions (DESIGN §2 rule 5). PG-proven equivalents already pass
(test_pg_acceptance 287/335/467/498; reconcile-zero 451/482/599;
conflict 530). Reconciliation proof is required after every receive.

## 4. Database security and exact privilege boundary

Runtime boundary (`stashtab_api`, staging only):
`inventory_item` SELECT + INSERT + UPDATE(stock, cost);
`purchase_record` SELECT + INSERT; `acquisition_lot` SELECT + INSERT;
`inventory_event` SELECT + INSERT; USAGE on the four `{table}_id_seq`
sequences. No DELETE/TRUNCATE/DDL/CREATEROLE/ownership/migrator
assumption anywhere; all other staging tables stay SELECT-only; worker
and readonly roles untouched. Column-scoped UPDATE is what keeps every
unrelated inventory write fail-closed. Verified consistent with
`_API_PRIVS`/`_assert_select_only` mechanics in
`inventory_live_schema/migrator.py` (the assert becomes per-table).

## 5. Application authentication/authorization

Verified Clerk bearer + `require_membership` via `get_shop_context`;
owner or staff may receive; `X-Shop-Id` remains an untrusted hint;
cutover stays owner-only (`_require_owner`); dev bypass off in staging
(P1-2). Compatible with the completed fail-closed identity slice
(D-025; `docs/fail-closed-shop-identity-v1/ACCEPTANCE.md`).

## 6. Idempotency and concurrency

Client-key resolution before any write; frozen canonical key
`purchase_record:{shop}:{purchase_record.id}` untouched (§7). Five
replay scenarios closed per amendment §6 with P1-1 correction applied.
The additive column cannot change truth identity: it lives on the live
row, is never concatenated into any idempotency key, and the lot/event
pair authority stays the frozen `(shop_id, idempotency_key)` uniques —
a NULL-key legacy row and a keyed row produce identical truth keys for
the same purchase id.

## 7. Cutover blast radius (after `complete` on the synthetic shop)

| Route | Logically enabled | Remains unavailable via |
| --- | --- | --- |
| New receive endpoint | Yes (intended) | — |
| `PATCH /inventory/{id}` quantity; `/reverse-adjust` | Gate passes | Missing `INSERT` on `inventory_adjustment` → controlled 503 |
| apply-trades; intake; staging commit; CSV import | Gate passes | Missing tables → controlled 503; frontend-locked |
| price approve/reject; approve-under-5 | No gate | Column-scoped denial + missing `sync_outbox` → controlled 503; read-only UI |
| resticker; label; settings; Shopify | No gate | Column-scoped denial or missing tables → controlled 503; frontend-locked |
| shops without a cutover row | No | Fail-closed 503, unchanged |

Controlled failures via the single 503 handler (P1 evidence requirement
test 7): no raw privilege/undefined-table 500 may surface.

## 8. Operations, rollback, evidence retention, liveness

Rollback disables the route and revokes grants back to SELECT-only via
the reviewed migrator; column, truth rows, purchase rows, and the
cutover row remain as evidence — no deletion, no drop, no rewrite.
`F2-TEST-0001` retained permanently as labeled staging proof. Liveness:
bounded correction rule (directive §7); timeouts are never green; a
`locking` cutover re-enters, `failed_permanent` stops for a new owner
decision.

## 9. Compatibility with slices 01–03 and staging identity/schema

- Slice-01 receive foundation: semantics reused verbatim; PG evidence
  carries over (14/14 ×2).
- Slice-02 outbound: untouched; outbound freeze gates unchanged.
- Slice-03 adjustments: code paths stay privilege-denied (containment
  by design); CSV owner-only and reason registry unchanged.
- Staging identity (D-025 fail-closed) and 13-table schema (D-027/
  D-028): compatible; exactly one additive nullable column under this
  amendment's vote; no forbidden table created (staging_item/
  pending_trades/sync_outbox stay absent).

## 10. Workflow governance and freeze mechanics

Vehicle is CONTRACT §6-compliant: versioned proposal, review against
frozen bodies (this record), acceptance-test additions, named human
approval, new version + freeze record. §15 manifest process is
non-self-hashing, mirrors `freezes/MANIFEST-SPEC.md`, updates the
validator's expected version in the same freeze step, and preserves §2/
§8/§9 history. No manifest is created by this packet.

## 11. Remaining decisions/blockers

- No blockers for the vote.
- Remaining human actions: the vote itself, then the four named
  unlocks (directive §1). Standing production gates (GATES.md:
  MIGRATOR-ROLE-PROVISIONING-GATE, runbook/audit/break-glass, zero
  recon) remain open and are NOT addressed by this amendment.

## 12. Freeze recommendation

**Recommend a human YES vote on AMENDMENT-1.3.0 as drafted (with the
pass-1 corrections already applied).** After approval, apply §14 diffs
and freeze exactly per §15 with manifest
`freezes/FREEZE-1.3.0.json`; run
`scripts/validate_inventory_truth_freeze.py` green before any
implementation unlock. Do not implement, provision, or cut over in the
same vote.

## 13. Confirmations

- Canonical receive key `purchase_record:{shop}:{purchase_record_id}`
  is unchanged; no new source, suffix, or grammar.
- The additive column cannot silently change truth identity (§6 above).
- Exact runtime privilege boundary recorded in §4.
- Rollback preserves all evidence (§8).
- Production exclusions: no production authorization, schema apply,
  privilege change, cutover, or deploy anywhere in this packet.
