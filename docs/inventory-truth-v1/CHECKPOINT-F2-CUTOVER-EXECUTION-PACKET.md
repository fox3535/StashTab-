# CHECKPOINT — F2 generation-1 cutover execution packet (planning + local proof only)

**Status:** `PREPARED — PROVEN LOCALLY — NOT EXECUTED — EXECUTION NOT APPROVED`
**Slice:** `inventory-truth-v1 / f2-slice-01-controlled-receive`
**Branch:** `docs/f2-cutover-execution-packet` from protected `main` at `aafae79`
**Prepared:** 2026-09-07 (local); disposable-harness runs recorded 2026-09-08 UTC (§4)
**Bound by:** AMENDMENT-1.3.0; frozen `DESIGN.md` / `MIGRATION.md`; D-045 decisions
1–7; `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §3–§7
**This file is not in any freeze hash.** No frozen packet file and no application
code was edited to produce it.

This checkpoint records an operator-safe **execution packet** for the F2
generation-1 cutover of **Smoke Shop B** and the **disposable-local proof** that
the packet's SQL behaves as claimed against the accepted schema. It authorises
nothing. Nothing here was run against staging, Neon, Railway, or Clerk. No
cutover row, receive, deploy, migration, privilege change, or code change
occurred. Execution still requires a **separate named cutover unlock**; the first
successful receive requires a **second** named unlock (D-045 decisions 3 and 4).

## 1. What this packet is

Seven deliverables, each a mutable artifact, none of them frozen contract text:

| # | Deliverable | File |
| --- | --- | --- |
| 1 | Runbook implementing operations-plan §3 steps 1–8 | `RUNBOOK-F2-CUTOVER-GEN1.md` |
| 2 | Exact PostgreSQL command set (preflight, baseline, locking, R1–R7, complete, verify, break-glass) | `scripts/f2-cutover/sql/` (12 files) |
| 3 | HTTP checks (401 unauthenticated, controlled 503 while locking, no successful receive) | `RUNBOOK-F2-CUTOVER-GEN1.md` §5 |
| 4 | Append-only operator audit template | `AUDIT-TEMPLATE-F2-CUTOVER-GEN1.md` |
| 5 | Credential handling (direct migrator session, no URL, secure removal, role retained) | `RUNBOOK-F2-CUTOVER-GEN1.md` §2 |
| 6 | Stop conditions S1–S11 and evidence-preserving recovery | `RUNBOOK-F2-CUTOVER-GEN1.md` §7–§8 |
| 7 | Disposable PostgreSQL 16 harness proving the SQL against the accepted schema | `scripts/f2-cutover/harness_f2_cutover.py` |

Two reviews accompany the packet:

- `reviews/REVIEW-F2-CUTOVER-R1-SQL.md` — the independent R1-against-frozen-1.3.0
  review required by operations-plan §5.
- `reviews/REVIEW-F2-CUTOVER-EXECUTION-PACKET.md` — the one bounded
  architecture / data-integrity / database-security / concurrency / operations /
  liveness review of the whole packet.

## 2. Authority and scope

The packet is the operator form of `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md`
§3 steps 1–8, ordered by D-045 decisions 3 and 4:

- reconciliation R1–R7 runs at **step 5 while the row is `locking`**;
- `complete` is written at **step 6** only if every invariant returned zero;
- the receive is **removed** from this runbook entirely — step 8 stops with no
  `POST`, behind a second named unlock.

Precedence applied throughout: frozen contract and amendments first, then
recorded decisions (D-045) and current context, then the operations plan. Where
the plan's prose and a frozen clause could be read differently, the frozen text
governs and the packet says so (see the R1 review §3.6). One deliberate deviation
from the plan's role labelling is recorded and justified in `RUNBOOK` §0.

## 3. Safety requirements — compliance

| Requirement | Where enforced | Proof |
| --- | --- | --- |
| Smoke Shop B pinned to `798d40f4-0832-46c4-991b-050e1310f6c4` | `lib-guards.sql` G1/G1b double-entry; every `WHERE shop_id = :'cutover_shop_id'` | harness H1c (malformed / disagreement / absent tenant all fail closed) |
| Generation 1 only | `lib-guards.sql` G2 (`:cutover_generation = 1`) | harness H2 (`f2_guard_generation_must_be_exactly_one`) |
| `F2-CUT-GEN1-0001` reserved, never used | `RUNBOOK` §5; `05-r1-r7.sql` R3b and `07` F8 assert it produced 0 rows | harness `_reserved_key_rows == 0`; reserved key probe returns `422` |
| No second generation, no second row | G2, W2/T3/BG5 rowcount discipline, `uq_cutover_shop_generation` | harness H2 (raw duplicate INSERT refused by the unique constraint) |
| No DELETE, TRUNCATE, fix-forward, seed, or receive | command-set write surface is exactly one INSERT + two UPDATEs (§5) | harness H8 catalog counts; `RUNBOOK` §3 "no retry inside the same unlock" |
| Global readiness flag does **not** become true | `RUNBOOK` §7; `features.inventory_cutover` is hard-coded `False` in `readiness.py`, unchanged | harness asserts `ready.json()["features"]["inventory_cutover"] is False` |
| Secrets parameterised, never embedded | libpq env vars only; no connection URL in any packet file | `lib-guards.sql` header §4; `RUNBOOK` §2 |
| Commands fail closed, transaction + error-stop | `ON_ERROR_STOP`, per-file `\set ON_ERROR_STOP on`, `BEGIN`/`COMMIT`, `SET TRANSACTION READ ONLY` on read steps | harness H5 (timeout / variance / missing var / wrong attestation all non-zero) |

## 4. Local proof — disposable PostgreSQL 16 harness (deliverable 7)

The harness is a throwaway, local-only pytest module. It is **not** collected by
`services/api`'s `pytest tests -q`, so it cannot affect backend CI. It never
contacts staging, production, Neon, Railway, or Clerk; never creates a real
credential; never issues DELETE or TRUNCATE; and treats any `2xx` from the
receive endpoint as a harness failure.

### 4.1 Two independent runs, each on fresh disposable databases

`python -m pytest scripts/f2-cutover/harness_f2_cutover.py` was invoked twice.
The suite is parametrised over `["first-fresh-db", "second-fresh-db"]` and the
`pg` fixture is function-scoped, so **every** test builds a brand-new
`postgres:16` container, provisions it from scratch, and destroys it at
teardown. Each invocation therefore proves the whole packet twice on fresh
databases; the two invocations are independent runs.

| Run | Finished (UTC) | Result | Duration |
| --- | --- | --- | --- |
| 1 | `2026-09-08T02:54:53Z` | `8 passed, 1 warning` | 56.83s |
| 2 | `2026-09-08T02:56:55Z` | `8 passed, 1 warning` | 56.20s |

Environment (identical for both runs): Windows; Python 3.12.10; pytest 9.1.1;
Docker 29.1.3; image `postgres:16` (`e17e86066e5e`); sqlalchemy 2.0.52;
fastapi 0.141.1; httpx 0.28.1. The single warning is a benign
`StarletteDeprecationWarning` about `httpx`/`starlette.testclient`, unrelated to
packet logic. After both runs `docker ps -a --filter name=stashtab-f2cut-` was
empty: no container leaked.

The 8 collected tests are the 4 methods below × the 2 fresh-db parameters:
`test_packet_sequence_is_deterministic_and_rerun_safe`,
`test_wrong_database_role_and_shop_fail_closed`,
`test_timeout_error_and_mismatch_cannot_pass`,
`test_locking_blocks_receive_and_break_glass_restores_it`.

### 4.2 The schema under test is the accepted schema, not a mock

`Pg16.provision()` builds each database with the **reviewed migrators**, in the
order their own post-verification forces: `identity_schema.migrator.apply`, then
`inventory_live_schema.migrator.apply_rehearsal` and `apply_f2_receive` (which
the harness asserts returns `indexes == ["uq_purchase_record_shop_client_key"]`
and non-empty `grants`), then `notifications_truth.migrator.apply_notification_schema`.
The identity baseline is D-045 decision 2 exactly: `shops = 2`, `shop_members = 2`,
with Smoke Shop B carrying its real pinned id and a control tenant that proves
the `complete` transition opens no one else's gate. Both rows are destroyed with
the container; nothing is seeded into staging and no operator command in `sql/`
inserts identity data.

### 4.3 Required behaviors → tests → evidence

| # | Required behavior | Test | Representative assertions |
| --- | --- | --- | --- |
| H1 | wrong database / role / shop fails closed | `test_wrong_database_role_and_shop_fail_closed` | G3 `f2_guard_unexpected_database`; G9 `f2_guard_session_is_not_the_expected_role`; W0b `..._w0b_session_cannot_insert_cutover_row`; G1/G1b/G8 for malformed, disagreeing, and absent tenants |
| H2 | duplicate generation fails closed | same | G2 `f2_guard_generation_must_be_exactly_one`; rerun refused by W0; raw duplicate INSERT refused by `uq_cutover_shop_generation` |
| H3 | `locking` keeps receive unavailable | `test_locking_blocks_receive_and_break_glass_restores_it` | unauthenticated `401`; authenticated-while-locking `503` with `error == FEATURE_NOT_READY`; still `503` after break-glass |
| H4 | R1–R7 zero checks are deterministic | `test_packet_sequence_is_deterministic_and_rerun_safe` | `05` run twice, all 14 `GATE_TOKENS` present and every `GATE_COLUMNS` value equal; `05b` run twice, stdout identical |
| H5 | timeout / error / mismatch cannot pass | `test_timeout_error_and_mismatch_cannot_pass` | missing var → `syntax error`; out-of-range timeout → `f2_gate_timeout_parameters_out_of_range`; held `ACCESS EXCLUSIVE` → `lock timeout`, no `R1-zero`; injected variance → `f2_gate_r1_snapshot_and_truth_variance`; overlay-reverse → `f2_gate_r1c_...`; wrong attestation → `f2_complete_t0_...` |
| H6 | `complete` affects only Smoke Shop B | `test_locking_blocks_receive_and_break_glass_restores_it` | exactly one row `(pinned, 1, complete, frozen_at, opened_at)`; control tenant probe `503`; `f3_open_gate_tenants == one-tenant-open` |
| H7 | break-glass returns only that row to `locking` | same | `bg2 one-row-withdrawn`; `bg3 evidence-preserved-status-only-changed`; `bg6 gate-reads-locking`; `id`/`created_at`/`frozen_at`/`opened_at` unchanged, `opened_at` not nulled |
| H8 | no evidence rows are deleted | both positive tests | `catalog_counts` before/after: only `inventory_truth_cutover` moves `(0 → 1)`; relation set unchanged; break-glass `bg4 all-row-counts-unchanged` and counts identical |
| H9 | rerun behavior is explicit and safe | three tests | step 1 rerun → `f2_preflight_p7_cutover_row_already_exists`; step 4 rerun idempotent (stdout identical); step 3 rerun → W0; step 6 rerun → `f2_complete_t0b_...`; break-glass rerun → `f2_break_glass_bg0c_...` |

### 4.4 HTTP checks are exercised over the real routers (deliverable 3)

`_api_client()` mounts the real `app.routers.admin` and `app.routers.health`
routers with the real `FeatureNotReadyError` / `OperationalError` /
`ProgrammingError` handlers, in `app_env = "staging"` with dev identity off, over
the runtime role. Probes and results:

| Probe | Expected | Observed |
| --- | --- | --- |
| Unauthenticated receive | `401` | `401` |
| Authenticated receive, Smoke Shop B, while `locking` | `503`, `error == FEATURE_NOT_READY` | `503`, `FEATURE_NOT_READY` |
| Reserved key `F2-CUT-GEN1-0001` (not a UUIDv4) | `422` before the gate | `422` (finding P1-1) |
| Missing `Idempotency-Key` | `422` | `422` |
| Control shop after Smoke Shop B reaches `complete` | `503` | `503` |
| `GET /api/v1/ready` | `features.inventory_cutover == false` | `false` |

`ProbeLog.record` asserts `status_code >= 300` on every probe and
`assert_no_success()` re-checks at the end, so **no successful receive is
performed** — the third side of the runbook §5 proof. `_envelope_counts` stays
`{purchase_record: 0, acquisition_lot: 0, inventory_event: 0, inventory_item: 0}`
and `_reserved_key_rows == 0` on the positive path.

## 5. Command set and write surface

Twelve LF-normalised files in `scripts/f2-cutover/sql/` (`.gitattributes` pins
`eol=lf` because psql keeps a trailing `\r` and that breaks `\ir`/`\echo`):
`lib-guards.sql`, `01-preflight.sql`, `02-baseline.sql`,
`02b-baseline-notification.sql`, `03-write-locking.sql`, `04-verify-locking.sql`,
`05-r1-r7.sql`, `05b-r5-notification.sql`, `06-write-complete.sql`,
`07-final-verification.sql`, `07b-verify-notification.sql`,
`08-break-glass-locking.sql`.

A scan of the whole command set for live write/DDL/privilege statements returns
exactly three, and nothing else:

| File:line | Statement | Purpose |
| --- | --- | --- |
| `03-write-locking.sql:50` | `INSERT INTO inventory_truth_cutover` | the one gen-1 `locking` row |
| `06-write-complete.sql:61` | `UPDATE inventory_truth_cutover` | `locking` → `complete`, `opened_at` |
| `08-break-glass-locking.sql:133` | `UPDATE inventory_truth_cutover` | break-glass `complete` → `locking`, status only |

There is **no** live `DELETE`, `TRUNCATE`, `DROP`, `ALTER`, `CREATE`, `GRANT`,
`REVOKE`, or `SET ROLE` anywhere in `sql/`. Every other occurrence of those
words is either a comment or a read-only `has_table_privilege` /
`has_column_privilege` catalog check (R7, P5/P6, W0b, T0c). Read-only steps wrap
their work in `BEGIN; SET TRANSACTION READ ONLY`, so "step 5 writes nothing" is a
database-enforced property, not a convention.

## 6. Independent R1 review (operations-plan §5 requirement)

`reviews/REVIEW-F2-CUTOVER-R1-SQL.md` reviews the R1 invariant
(`05-r1-r7.sql` R1a/R1c/R1d/R1b/R1e and its step-7 re-evaluation as F4) against
frozen `DESIGN.md` §1 and `MIGRATION.md`, and the accepted `core.reconcile_shop()`,
`models_truth.InventoryEvent`, `models/inventory.InventoryItem`, and the reviewed
`inventory_live_schema.migrator` DDL. Verdict: `PASS WITH ONE RECORDED CONTRACT
GAP`. The R1b query reproduces `reconcile_shop()` exactly (FULL OUTER JOIN plus
the `snapshot_stock IS NULL` arm plus `COALESCE`-to-zero), adds a sound aggregate
arm, excludes `acquisition_lot.quantity_acquired`, and proves overlay hygiene and
one-stock-row-per-SKU as preconditions rather than assuming them.

Finding **R1-1** (P2, recorded for an owner decision, not a stop for this packet):
`ck_overlay_zero_delta` (`models_truth.py` L82–L86) does not enforce the frozen
`reverse`-of-overlay clause of `DESIGN.md` L20–L21/L29–L31. R1c arms (c)/(d)
close the gap at the gate; the schema reconciliation is an application-code and
frozen-contract matter outside this packet's authority and is unreachable at
step 5 (zero event rows for the pinned tenant).

## 7. Bounded multi-discipline review

`reviews/REVIEW-F2-CUTOVER-EXECUTION-PACKET.md` is the single bounded review
across architecture, data-integrity, database-security, concurrency, operations,
and liveness. Verdict: `PASS`. It records finding **P1-1** — the reserved key
`F2-CUT-GEN1-0001` is not a UUIDv4, so `_validated_client_key`
(`admin.py` L1220–L1229) rejects it with `422` and it cannot serve as the first
receive's `Idempotency-Key` under the later unlock. This is a forward-looking
owner decision for the **receive** unlock, not a stop for this planning-only
packet, which never receives and correctly leaves the key unused. No correction
pass was required: the packet is internally consistent, the harness passes twice,
and every finding is a recording rather than a defect in this packet's behavior.

**P1-1 resolved by D-046 (2026-09-08, option (a)).** Frozen UUIDv4 validation
(`AMENDMENT-1.3.0` §5 and `_validated_client_key`) stays authoritative and is
**not** amended; no application code, schema, test, workflow, or dependency
changed. The reserved receive `Idempotency-Key` for the later
one-POST/one-replay first-receive proof is now the UUIDv4
`6f91b921-0c9d-4c75-8f54-6da9e74ef8f2`; `F2-CUT-GEN1-0001` is retained only as a
rejected `422`/no-write control probe (H-3b). Both keys remain unused, the
receive remains locked behind its own separate named unlock, and R1-1 remains a
separate named schema concern to close before any receive. This packet was merged
to protected `main` as `f0b0ebb` (PR #37); recording the decision executed
nothing.

## 8. Not done by this packet (explicit)

No contact with Railway, Neon, or Clerk. No credential created. No staging SQL
executed. No staging reconciliation. No cutover altered. No receive called. No
deploy, redeploy, autodeploy enablement, migration, or privilege change. No
production contact. No edit to any frozen contract, design, migration, test,
amendment, or `GATES.md` text. No application-code change. No claim that the
global readiness flag becomes true. No direct commit or push to `main`.

## 9. Packet manifest and classification

Mutable artifacts authored by this packet (all new except `.gitattributes`):

- `docs/inventory-truth-v1/RUNBOOK-F2-CUTOVER-GEN1.md`
- `docs/inventory-truth-v1/AUDIT-TEMPLATE-F2-CUTOVER-GEN1.md`
- `docs/inventory-truth-v1/CHECKPOINT-F2-CUTOVER-EXECUTION-PACKET.md` (this file)
- `docs/inventory-truth-v1/reviews/REVIEW-F2-CUTOVER-R1-SQL.md`
- `docs/inventory-truth-v1/reviews/REVIEW-F2-CUTOVER-EXECUTION-PACKET.md`
- `scripts/f2-cutover/harness_f2_cutover.py`
- `scripts/f2-cutover/sql/*.sql` (12 files)
- `.gitattributes` (adds `scripts/f2-cutover/**/*.sql text eol=lf`)

Explicitly **excluded** from this packet's commits: pre-existing untracked
application artifacts that are not part of the cutover packet
(`lib/use-api-auth.ts`, `services/api/app/static/barcodes/*.png`) and generated
`scripts/f2-cutover/__pycache__/`. Frozen packet files and application code were
left untouched.

## 10. Relationship to other records

- Authority: `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §3–§7; D-045 in
  `docs/agent-context/DECISIONS.md`.
- Pre-cutover baseline: `CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`,
  `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`.
- Where execution evidence will be recorded after a named unlock:
  `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`; live gate status
  `GATES-POINTER-F2-SLICE-01.md` (frozen `GATES.md` unchanged).

## 11. Next action

This packet is `PREPARED — PROVEN LOCALLY`. The next state,
`RUNBOOK APPROVED — READY FOR NAMED UNLOCK`, requires verbatim approval of
`RUNBOOK` §3–§7 and a **separate** named cutover unlock that names the shop, the
actor, the reserved key, and the scope. D-045 is not that unlock. The first
successful receive requires a **second** named unlock; finding P1-1 is now
resolved by D-046 (the reserved receive key is the UUIDv4
`6f91b921-0c9d-4c75-8f54-6da9e74ef8f2`), but R1-1 remains a separate named
schema concern to close before any receive. Merge, deploy, migration, and any
cloud write remain separately
gated and are not authorised here.
