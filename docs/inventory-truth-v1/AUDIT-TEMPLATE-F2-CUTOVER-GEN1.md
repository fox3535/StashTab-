# AUDIT TEMPLATE — F2 generation-1 cutover, Smoke Shop B

**Append-only.** Copy this file once per attempt to
`AUDIT-F2-CUTOVER-GEN1-<UTC-yyyymmddThhmmssZ>.md` before step 1 and fill it in
as the attempt proceeds. Never edit a completed record, never delete a line,
never rewrite a stopped attempt to look successful. A correction is a new
appended line with a wall clock and a reason, leaving the original visible.

Authority: `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §4, and D-045 decisions 1,
2, 5 and 7. Procedure: `RUNBOOK-F2-CUTOVER-GEN1.md`.

**Never record a credential, connection string, password, token, session cookie,
or URL containing any of them.** Record role **names** only. If a value must be
referenced, name where the owner holds it.

---

## A. Attempt identification

| Field | Value |
| --- | --- |
| Attempt id | `F2-CUT-GEN1-ATTEMPT-____` |
| Audit file | |
| Unlock reference (names shop, actor, key, scope) | |
| Runbook commit (exact SHA) | |
| Command set commit (exact SHA) | |
| Target database | `stashtab_staging` |
| Target environment | staging (never production) |
| Tenant | Smoke Shop B |
| `shop_id` | `798d40f4-0832-46c4-991b-050e1310f6c4` |
| Generation | `1` |
| Reserved key (must stay unused) | `F2-CUT-GEN1-0001` |
| Outcome (fill last) | `COMPLETED-STOPPED-AT-STEP-8` / `STOPPED-S__` / `BREAK-GLASS` |

## B. Actors

| Role in this attempt | Identity recorded | Notes |
| --- | --- | --- |
| Owner (authorises, present throughout) | name | |
| Operator (executes the SQL) | name + Clerk user id | |
| Second person (two-person rule) | name | |
| Database write role | `stashtab_migrator` | role name only, never a credential |
| Runtime role asserted | `stashtab_api` | |
| Other roles asserted | `stashtab_worker`, `stashtab_readonly` | |
| Receive actor (step 4/7 probes only) | Clerk user id | no successful receive is performed |

## C. P0 preconditions (runbook §1) — all must be ticked before step 1

| # | Precondition | Evidenced by | Tick | Wall clock |
| --- | --- | --- | --- | --- |
| P0-1 | Named unlock recorded | unlock text | | |
| P0-2 | Runbook approved verbatim; plan §3–§7 unchanged | review record | | |
| P0-3 | Two-person rule in force | §B | | |
| P0-4 | Target is `stashtab_staging`, not production | `PGDATABASE`, P-preflight G3 | | |
| P0-5 | Railway autodeploy off | Railway console observation | | |
| P0-6 | No worker, no cron | log window | | |
| P0-7 | Exactly one API process | log window | | |
| P0-8 | No open incident | incident tracker | | |
| P0-9 | `inventory_truth_cutover` empty | `01-preflight.sql` P7 | | |
| P0-10 | Audit file created and open | this file | | |

Any unticked line is **S11**: stop before writing anything.

## D. Step log — append one row per step, in order

| Step | File / probe | Wall clock start | Wall clock end | psql exit | Tokens / values observed | Actor |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | session open + `ready` | | | n/a | `current_user`, `session_user`, `current_database()`, `version()`, HTTP status | |
| 2 | `01-preflight.sql` | | | | P1–P8 | |
| 2 | `02-baseline.sql` | | | | digests (→ §E) | |
| 2 | `02b-baseline-notification.sql` | | | | `r5_notification_digest` (→ §E) | |
| 3 | `03-write-locking.sql` | | | | W0, W0b, W2, W3 + row (→ §F) | |
| 4 | `04-verify-locking.sql` | | | | V1–V7 | |
| 4 | H-1, H-2, H-3, H-3b, H-4 | | | n/a | statuses (→ §G) | |
| 5 | `05-r1-r7.sql` | | | | all §6 tokens (→ §H) | |
| 5 | `05b-r5-notification.sql` | | | | `R5b-unchanged`, `R5b-zero-rows-for-pinned-shop` | |
| 6 | `06-write-complete.sql` | | | | T0, T0b, T0c, T1–T4 + row (→ §F) | |
| 7 | `07-final-verification.sql` | | | | F1–F9 (→ §H) | |
| 7 | `07b-verify-notification.sql` | | | | F10, F11 | |
| 7 | H-3, H-4 | | | n/a | statuses (→ §G) | |
| 8 | stop + credential destroyed | | | n/a | see §K | |

## E. Hashes and digests

Copy the exact 32-character values printed. Do not retype them from memory. A
transcription error is caught later by a digest mismatch, which is the intended
behaviour.

| Name | Source | Value |
| --- | --- | --- |
| `baseline_digest` (13 relations, incl. cutover) | `02-baseline.sql` | |
| `baseline_excl_cutover` (12 relations) | `02-baseline.sql` | |
| `base_r5_inventory` (6 out-of-envelope) | `02-baseline.sql` | |
| `base_r5_notification` (12 notification) | `02b-baseline-notification.sql` | |
| `freeze_window_start` | `02-baseline.sql` B0 | |
| `freeze_window_end` | `07-final-verification.sql` F0 | |
| `bg_pre_digest` (only if break-glass ran) | `08-break-glass-locking.sql` BG1 | |

Per-relation baseline rows (total / pinned-shop) — paste the full aligned output
of `02-baseline.sql` B1 and `02b-baseline-notification.sql` N1 below:

```text
<paste>
```

## F. The cutover row, exactly as written

Paste the `SELECT` output verbatim. One block per state change; never overwrite
an earlier block.

**After step 3 (`W4`) — expect `locking`, `frozen_at` set, `opened_at` NULL:**

```text
<paste id | shop_id | generation | status | frozen_at | opened_at | created_at>
```

**After step 6 (`T5`) — expect `complete`, both timestamps set,
`opened_at >= frozen_at`, same `id` as above:**

```text
<paste>
```

**After break-glass (`BG0` / final `SELECT`) — only if §J was invoked. Expect the
same `id`, `created_at`, `frozen_at` and `opened_at`, with `status` back to
`locking`:**

```text
<paste>
```

Row-count discipline observed at each point (must be `1` / `0` / `0`):

| Point | total rows | rows for other shops | rows for other generations |
| --- | --- | --- | --- |
| step 3 (W2) | | | |
| step 5 (R4) | | | |
| step 6 (T3) | | | |
| step 7 (F7) | | | |

## G. HTTP probe record

One row per probe. Record the status and the body's `error` / `feature` fields.
Never record the bearer token.

| Probe | Wall clock | Endpoint | Shop | Authenticated | `Idempotency-Key` shape | HTTP status | Body `error` / `feature` | Railway request id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H-1 | | `/api/v1/admin/inventory/receive` | Smoke Shop B | no | fresh UUIDv4 | expect `401` | | |
| H-2 | | same | Smoke Shop B | yes | fresh UUIDv4 | expect `503` | `FEATURE_NOT_READY` / `inventory_truth` | |
| H-3 | | same | other shop | yes | fresh UUIDv4 | expect `503` | | |
| H-3b | | same | Smoke Shop B | yes | `F2-CUT-GEN1-0001` (not a UUIDv4) | expect `422` | | |
| H-4 | | `/api/v1/ready` | n/a | n/a | n/a | expect `200`, `reasons: []` | | |
| H-4 (step 7) | | `/api/v1/ready` | n/a | n/a | n/a | expect `200`, `reasons: []` | | |
| H-3 (step 7) | | receive | other shop | yes | fresh UUIDv4 | expect `503` | | |

`ready` payload recorded at step 1 and step 7 (paste both; `inventory_cutover`
must be `false` in both — this packet never changes it):

```text
<paste step 1>
<paste step 7>
```

**No successful receive was performed.** All three sides of the proof are
required:

| Proof side | Evidence | Observed |
| --- | --- | --- |
| Every probe returned `>= 300` | §G, all rows | |
| Envelope empty for the pinned shop | `04` V6 and `07` F8 | |
| Reserved and probe markers absent | `04` V7 and `07` F8 third clause | |

Bounded Railway log window covering the attempt (start/end wall clock, one
startup marker, request lines and status codes) — paste or attach the path:

```text
<paste or path>
```

## H. R1–R7 gate record (step 5, while `locking`)

Every invariant must be exactly zero. **A timeout, an error, a partial response
or a missing token is a failure, not a pass.**

| # | Invariant | Token required | Observed | Notes |
| --- | --- | --- | --- | --- |
| R1 | snapshot vs append-only truth | `R1-zero` | | |
| R1c | overlay events carry `quantity_delta = 0` | `overlay-deltas-are-zero` | | |
| R1d | `uq_inventory_shop_sku` present | `one-stock-row-per-sku` | | |
| R2 | receive envelope completeness | `R2-zero` | `r2_rows_examined = ____` → **trivial** zero over 0 rows |
| R3 | idempotency uniqueness | `R3-zero` | **trivial** zero; reserved key produced 0 rows |
| R4 | cutover row discipline at `locking` | `R4-zero` | |
| R5a | out-of-envelope inventory digest | `R5a-unchanged` | |
| R5b | all 12 notification relations | `R5b-unchanged` + `R5b-zero-rows-for-pinned-shop` | from `05b` |
| R5c | envelope empty for pinned shop | `R5c-envelope-empty` | |
| R6 | identity invariance | `R6-zero` | `shops = 2`, `shop_members = 2` |
| R7a | envelope table grants | `R7a-zero` | |
| R7b | USAGE on the four F2 sequences | `R7b-zero` | |
| R7c | PUBLIC holds nothing | `R7c-zero` | |
| R7d | worker/readonly hold nothing | `R7d-zero` | |
| R7e | cutover write path | `R7e-zero` | |
| — | evaluation point | `gate_evaluation_point = evaluating-at-locking` | |
| — | notification evaluation point | `nb1_evaluation_point = evaluating-at-locking` | |

R2 and R3 are recorded as **trivial pre-receive zeros** under D-045 decision 4.
They are not receive proofs. They become substantive when re-run under the later
receive unlock.

Step 7 re-verification:

| Check | Token required | Observed |
| --- | --- | --- |
| F1 R4 at `complete` | `R4-zero-at-complete` | |
| F2 gate reads `complete` | `gate-reads-complete` | |
| F3 exactly one tenant open | `one-tenant-open` | |
| F4 R1 re-evaluated | `R1-zero` | |
| F5 R6 | `R6-zero` | |
| F6 baseline excluding the cutover row | `baseline-unchanged-excluding-cutover-row` | |
| F6b out-of-envelope digest | `R5a-unchanged-at-step-7` | |
| F7 cutover rowcount | `cutover-rowcount-1` | |
| F8 no receive performed | `no-receive-performed` | |
| F10 notification digest at step 7 | `R5b-unchanged-at-step-7` | |
| F11 zero notification rows, pinned shop | `R5b-zero-rows-for-pinned-shop` | |

Timeouts used (must be inside the guarded ranges):

| Variable | Value |
| --- | --- |
| `recon_timeout_ms` | |
| `lock_timeout_ms` | |
| `verify_timeout_ms` | |
| `break_glass_timeout_ms` | |

## I. Stop conditions S1–S11 — record every one, invoked or not

An attempt with no stop still records all eleven as `not invoked`. That is the
evidence that each was considered.

| # | Trigger | Invoked? | Wall clock | Exact detection (`stashtab_f2.*` name, HTTP status, or observation) | Evidence preserved | First action taken |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | write affects more than the named shop, or more than one row | | | | | |
| S2 | non-cutover shop not `503`, or Smoke Shop B not `503` while `locking` | | | | | |
| S3 | any R1–R7 invariant non-zero | | | | | |
| S4 | reconciliation errors, times out, or cannot complete | | | | | |
| S5 | unexpected privilege, or a role can assume the migrator | | | | | |
| S6 | any write outside the F2 envelope | | | | | |
| S7 | duplicate idempotency key produced a second row | | | | | |
| S8 | API restart/crash, or a new deployment in the window | | | | | |
| S9 | suspected credential exposure | | | | | |
| S10 | `ready` not `200` with `reasons: []`, incl. `truth_migrator_role` | | | | | |
| S11 | any P0 precondition not evidenced | | | | | |

Evidence preserved (all attempts, including stopped ones): the full psql stdout
and stderr for every file that ran, the HTTP statuses and bodies, the log window,
and the digests in §E. Attach paths or paste below. Nothing is deleted, and no
row is removed from any table.

```text
<paths or paste>
```

## J. Break-glass record — only if invoked

| Field | Value |
| --- | --- |
| Declared at (wall clock) | |
| Trigger (runaway writes / cross-tenant visibility / privilege escalation / unrecoverable mid-transaction error) | |
| Authorising human owner | |
| Was this a way past a failed reconciliation? | must be `NO` — if R1–R7 were non-zero, break-glass is forbidden; stop under S3 |
| `break_glass_attestation` supplied | `owner-authorized-break-glass` |
| BG0 pre-image `id` / `created_at` / `frozen_at` / `opened_at` | |
| BG2 `one-row-withdrawn` | |
| BG3 `evidence-preserved-status-only-changed` | |
| BG4 `all-row-counts-unchanged` | |
| BG6 `gate-reads-locking` | |
| H-2 re-probe after withdrawal | expect `503` |
| Post-withdrawal snapshot vs step-2 baseline | |
| Grant rollback run? | only if grants changed; never widens grants |
| Redeploy / restart performed? | must be `NO` |
| Incident record opened | |
| Further attempts frozen | `YES` — no retry inside this unlock |

## K. Credential lifecycle

| Field | Value |
| --- | --- |
| Session opened (wall clock) | |
| Credential transport | libpq env vars `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE=require` — **no URL anywhere** |
| Credential ever written to a file? | must be `NO` |
| Credential ever placed in Railway or app configuration? | must be `NO` |
| Credential ever printed, logged, committed, or pasted into this record? | must be `NO` |
| `stashtab_truth_migrator_role` present in the app environment at any point? | must be `NO` (otherwise S10) |
| Client container used? destroyed? | |
| Session closed (wall clock) | |
| Temporary local credential destroyed (wall clock) | |
| Destruction method | env vars removed; shell history cleared; client container removed |
| Neon `stashtab_migrator` role **retained** | must be `YES` — the role is not deleted |
| Owner rotated the credential? | only under S9; record the event, never a value |

## L. Final decision

| Field | Value |
| --- | --- |
| Steps completed | 1 2 3 4 5 6 7 8 (circle the last one reached) |
| Final `cutover_status` for Smoke Shop B | `locking` / `complete` |
| Row count in `inventory_truth_cutover` | must be `1` |
| Other tenants' gates | must all be closed (`503`) |
| `features.inventory_cutover` | `false` — unchanged, and this attempt does **not** claim otherwise |
| Global readiness flag | **not** claimed true |
| Successful receive performed | must be `NO` |
| `F2-CUT-GEN1-0001` used | must be `NO` — still reserved for the later receive unlock |
| Second generation created | must be `NO` |
| Any DELETE, TRUNCATE, fix-forward, or seed | must be `NO` |
| Frozen packet files edited | must be `NO` |
| Application code edited | must be `NO` |
| Decision | `ACCEPTED — CUTOVER COMPLETE, RECEIVE STILL LOCKED` / `STOPPED — <S#>` / `WITHDRAWN — BREAK-GLASS` |
| Decided by | |
| Decision wall clock | |
| Next action | `R` record item: update `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`, close the operations plan, update the gate pointer — on a new branch with a PR. Never a direct commit or push to `main`. The first successful receive requires the **separate** named unlock of D-045 decision 4. |

## M. Appended corrections

Append only. Never edit a line above.

| Wall clock | Actor | Line corrected | Original value | Corrected value | Reason |
| --- | --- | --- | --- | --- | --- |
| | | | | | |
