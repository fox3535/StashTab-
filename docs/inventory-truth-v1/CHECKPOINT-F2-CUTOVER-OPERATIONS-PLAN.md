# Cutover operations plan — F2 gen-1 staging cutover (planning only)

**Status:** `OWNER DECISIONS RECORDED — PLANNING ONLY — EXECUTION NOT APPROVED — NOT EXECUTED`
**Slice:** `inventory-truth-v1 / f2-slice-01-controlled-receive`
**Prepared on:** `docs/f2-cutover-operations-plan` from `main` at `0a244a5`
**Prepared:** 2026-09-04 (D-044); PR #34 merged 2026-09-05T01:49:31Z
**Merged on `main`:** PR #35 merge commit `9266e2a`, 2026-09-07T14:11:48Z
**Owner decisions recorded:** 2026-09-07 (D-045) on
`docs/f2-cutover-owner-decisions` from `main` at `9266e2a`
**Bound by:** AMENDMENT-1.3.0; frozen `GATES.md` §“Standing deployment gates” 3
and 4; `CHECKPOINT-F2-CUTOVER-PLANNING.md`
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

This plan authorizes nothing. No cutover row, no receive, no deploy, no
privilege change, and no code change occurred while it was written or while the
owner decisions below were recorded. The seven decisions in §2 are now
**answered** in §2.1 and recorded as decision entry **D-045**. Recording them is
not an execution approval: a separate named cutover unlock is still required, and
the first successful receive requires a second one.

## 1. Mechanism as implemented (read from code, not assumed)

| Fact | Source |
| --- | --- |
| Staging/production gate: receive is open only when `cutover_status(db, shop_id) == "complete"`, otherwise `FeatureNotReadyError("inventory_truth")` → controlled **503** | `services/api/app/feature_readiness.py` — `ensure_inventory_mutations_ready` |
| `cutover_status` reads the **first** `inventory_truth_cutover` row matching `shop_id` and returns its `status`, or `None`; it does not order by `generation` | `services/api/app/inventory_truth/core.py` |
| Row shape: `shop_id` varchar(36), `generation` int default `1`, `status` varchar(20) default `locking`, `frozen_at`, `opened_at`, `created_at`; unique `(shop_id, generation)` as `uq_cutover_shop_generation` | `services/api/app/inventory_truth/models_truth.py` |
| The gate runs **before** `_attempt(...)` and the single `db.commit()`; `ReceiveFrozenError` is re-raised as `FeatureNotReadyError` | `services/api/app/logic/controlled_receive.py` |
| Runtime `stashtab_api` holds **SELECT only** on `inventory_truth_cutover` — it cannot insert or update the cutover row | `services/api/tests/test_f2_receive_pg.py` (SELECT-only assertion); confirmed read-only on staging |
| `features.inventory_cutover` is **hard-coded `False`**; it is not derived from the per-shop row | `services/api/app/readiness.py` |
| `/api/v1/ready` returns **503 `not_ready`** as soon as `reasons` is non-empty, and `prohibited_feature_reasons()` adds `truth_migrator_role` if a truth-migrator role is configured in the app environment | `services/api/app/readiness.py`, `feature_readiness.py` |

Planning consequences:

- Cutover is **per shop**, not global: exactly one row for one named gen-1
  synthetic shop. Every other shop must stay fail-closed.
- The cutover write needs a credential **outside** the runtime envelope, because
  the pooled runtime role is SELECT-only on the cutover table and the F2 objects
  are owned by `stashtab_migrator`. This is owner decision 1 and the main
  governance risk in the whole slice.
- The app environment must **not** carry a truth-migrator role: doing so flips
  `/api/v1/ready` to `503` with reason `truth_migrator_role`. Ready `200` with
  `reasons: []` is therefore a pre- and post-condition of the runbook, and a
  built-in detector against smuggling the credential into the service.
- Post-cutover verification must **not** expect `/api/v1/ready` to change. The
  evidence is the cutover row itself plus the receive outcome. Making that flag
  reflect per-shop state would be a code change and a separate slice.
- Because `cutover_status` takes the first matching row unordered, **exactly
  one** cutover row per shop may exist. A second generation for the same shop
  would make the gate non-deterministic; gen-1 only, and any later generation
  needs a contract-level decision, not an operational one.

## 2. Owner decisions required before execution

1. **Cutover write credential.** Which role writes the row (the `stashtab_migrator`
   owner path, or a time-bounded owner SQL session), how it is delivered, who
   holds it, and how it is destroyed afterwards. It must never be stored in
   application configuration or the runtime container.
2. **Named gen-1 synthetic shop.** The exact `shop_id`, its owner membership, and
   whether that shop already exists in the staging identity baseline
   (`shops = 2` / `shop_members = 2`) or must be created first — creation would
   be an identity write and needs its own explicit authorization.
3. **Row content and status path.** `generation = 1`; whether `status` goes
   directly to `complete` or passes through `locking` with `frozen_at` /
   `opened_at` set; who signs off the written row.
4. **Receive authorization.** Whether one successful receive is authorized inside
   the same unlock, or requires a second named unlock after reconciliation.
5. **Idempotency key.** The exact `purchase_record.client_idempotency_key` value
   or format for the first receive (max 36 characters), and the replay
   expectation for a second POST with the same key.
6. **Reconciliation acceptance.** Approval of the R1–R7 invariants in §5 as the
   zero-variance gate, plus where the audit record in §4 is stored.
7. **Ready-flag expectation.** Explicit acceptance that
   `features.inventory_cutover` stays `false` after a per-shop cutover.

### 2.1 Recorded answers (D-045, 2026-09-07)

The owner approved all seven decisions. They are **recorded only**: recording
them creates no credential, writes no row, schedules no cutover, and approves no
execution.

1. **Cutover write credential** — one **time-bounded direct session** as
   `stashtab_migrator`. The credential is held privately by Chris, is **never**
   added to Railway or to application configuration, and is securely deleted
   after the session. “Revoke” means destroying the temporary
   credential/session — **not** deleting the Neon migrator role.
2. **Named gen-1 synthetic shop** — existing **Smoke Shop B** only, `shop_id`
   `798d40f4-0832-46c4-991b-050e1310f6c4`. No shop or membership is created or
   changed, so the staging identity baseline (`shops = 2` / `shop_members = 2`)
   is both a precondition and a postcondition.
3. **Row content and status path** — `generation = 1` only. Write `locking` with
   `frozen_at`; run and record **R1–R7 while locked**; only after every check
   passes, write `complete` with `opened_at`. Both writes use the same controlled
   migrator session, in separate transactions where required. **Never** create a
   second generation and **never** delete the row.
4. **Receive separation** — cutover and reconciliation are **one** future unlock.
   The first successful receive requires **another separate named unlock**.
5. **Future receive idempotency key** — `F2-CUT-GEN1-0001` is reserved. One POST
   and one replay are permitted **only** after the later receive unlock. Neither
   earlier probe/test key (`F2-PROBE-DO-NOT-USE`, `F2-TEST-0001`) may be reused.
6. **Reconciliation acceptance** — **R1–R7 approved verbatim** as the
   zero-variance gate. A timeout, partial response, exception, or mismatch is a
   **failure**; success requires zero variance. Evidence belongs in the mutable
   acceptance record plus the append-only database evidence. **Never** fix
   forward and **never** delete evidence during the proof.
7. **Ready flag** — accepted that the global `features.inventory_cutover` may
   remain `false` after this per-shop cutover. The readiness code is **not**
   changed in this slice. The shop-scoped cutover row and the reconciliation
   evidence govern this proof.

Consequences that follow from these answers, recorded rather than assumed:

- Decision 3 **re-orders §3**: reconciliation runs while the row is `locking`,
  before `complete` is written. Phase 3 therefore splits into two writes with
  phase 6 between them.
- While `status = 'locking'`, `cutover_status(db, shop_id)` is not `"complete"`,
  so an authenticated receive for Smoke Shop B must **still return `503`**. That
  is itself a check that the gate is driven by `status` and not by row existence.
- Because decision 4 defers the receive, at cutover time R2 and R3 evaluate
  against **zero** receive rows and must return zero trivially; they become the
  substantive test when re-run under the later receive unlock.
- Decision 2 gives R6 an exact expected value: `shops = 2` and
  `shop_members = 2`, unchanged.
- Decision 1 plus §1 means ready `200` with `reasons: []` must hold before and
  after: the migrator session is direct and time-bounded, so
  `stashtab_truth_migrator_role` must stay absent from the app environment.

## 3. Runbook (draft — executes only under a named unlock)

| Phase | Actor | Action | Expected evidence | Stop if |
| --- | --- | --- | --- | --- |
| 0 Preconditions | Owner + operator | Named unlock recorded; this plan approved; two-person rule in force; staging only; autodeploy off; no open incident | Unlock text names shop, actor, key, and scope | Any precondition is unverifiable |
| 1 Baseline | Operator (pooled `stashtab_api`, read-only) | Snapshot row counts, digest, cutover rowcount, identity counts, column/index/grants | Digest equals the recorded pre-cutover baseline; cutover rowcount `0` | Digest differs, or any cutover row already exists |
| 2 Freeze window | Operator | Confirm one API process, no worker/cron, no other writer; record window start (wall clock) | Bounded log window with one startup marker | A second process, worker, cron, or new deployment appears |
| 3 Cutover write | Owner-approved credential (outside runtime role) | Single `INSERT` for the named shop: `generation = 1`, `status = 'complete'`, timestamps set | `SELECT` shows exactly one row for that shop, zero for all others | More than one row, or any other shop affected |
| 4 Gate check | Operator | `GET /api/v1/ready`; unauthenticated receive; receive for a **different** shop | Ready `200` with `reasons: []` unchanged; unauthenticated `401`; other shop still `503` | Ready changes, or any other shop’s gate opens |
| 5 Single receive | Owner-named Clerk actor | Only if decision 4 allows: one `POST` with the named idempotency key, then one replay of the same key | First call succeeds with the documented envelope; replay returns the documented idempotent no-op | Any second distinct write, or a replay creates a row |
| 6 Reconcile | Operator (read-only) | Run R1–R7 in §5 before declaring success | Every invariant exactly zero variance | Any non-zero, error, or timeout |
| 7 Record | Operator | Write evidence into `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`, close this plan, update the gate pointer; branch + PR | Draft PR against `main`; validators green | Direct commit or push to `main` |

**Authoritative ordering after D-045 decision 3.** Phase 3 is split into two
writes with phase 6 between them, inside the same controlled migrator session:

1. Write `generation = 1`, `status = 'locking'`, `frozen_at` set, for Smoke Shop
   B only. Confirm exactly one row for that shop and zero for every other shop.
2. Confirm the gate is still closed: an authenticated receive for Smoke Shop B
   returns `503`, and `/api/v1/ready` is unchanged at `200` with `reasons: []`.
3. Run phase 6 reconciliation **while locked**. Any non-zero, error, or timeout
   stops the attempt with the row left at `locking`.
4. Only if R1–R7 are all exactly zero, write `status = 'complete'` with
   `opened_at` as a separate transaction.

Phases 4 and 5 then follow `complete`, and phase 5 runs **only** under the
separate receive unlock required by decision 4. The row is never deleted;
withdrawal is the status change described in §6 step 2.

Phase 1 and phase 6 use the same read-only pooled-role pattern already proven in
`CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`: read-only session, no migrator
credential, connection URL never printed, environment cleared after use.

## 4. Audit record (append-only)

Captured for every attempt, successful or stopped:

- Wall-clock start/end of each phase, and the freeze-window boundaries.
- Actor identity: the Clerk user id for the receive actor; the **role name** only
  for the cutover write — never a credential, connection string, or token.
- The cutover row exactly as written (`SELECT` output) and as withdrawn, if it
  was.
- Pre- and post-cutover row-count digests, and the reconciliation outputs.
- The idempotency key used, and the resulting `purchase_record`,
  `acquisition_lot`, and `inventory_event` rows — append-only evidence; grant
  rollback restores SELECT-only while preserving the column, index, and evidence
  rows (§12 policy, as recorded in
  `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`).
- The bounded Railway log window covering the attempt, with request lines and
  status codes.
- Any stop or break-glass invocation: trigger, authorizing human, actions taken,
  and resulting state.

Retention: no auto-delete of unresolved exceptions or audit history until a
policy exists (open follow-up in frozen `GATES.md`). Audit records live in
repository documents and the append-only tables; chat transcripts are not durable
project memory.

## 5. Zero-reconciliation gate

All checks are read-only through the pooled runtime role. **Timeout is not
green**: an errored, partial, or unfinished reconciliation is a failure and
triggers §7.

| # | Invariant | Zero condition |
| --- | --- | --- |
| R1 | Legacy snapshot vs append-only truth for the cutover shop | `sum(inventory_item.stock)` for the shop equals the quantity derived from truth events for the same shop; variance exactly `0` |
| R2 | Receive envelope completeness | Every `purchase_record` row for the shop has a matching `acquisition_lot` and at least one `inventory_event`; orphan count `0` |
| R3 | Idempotency uniqueness | No duplicate `(shop_id, client_idempotency_key)`; a replayed key produced `0` additional rows |
| R4 | Cutover row discipline | Exactly `1` row for the named shop with `generation = 1` and `status = 'complete'`; `0` rows for every other shop |
| R5 | Out-of-scope writes | `0` new rows outside the F2 envelope (`sale`, `refund_record`, `return_record`, `inventory_adjustment`, `inventory_channel_observation`, `inventory_exception`) and `0` rows in notification tables |
| R6 | Identity invariance | `shops` and `shop_members` counts equal the declared baseline; any intended change must be named in the unlock |
| R7 | Privilege invariance | Envelope grants unchanged: SELECT + INSERT on the four envelope tables, `UPDATE (stock, cost)` on `inventory_item` only, no table-wide UPDATE/DELETE/TRUNCATE, USAGE on the four F2 sequences |

R1’s exact SQL must be written against the frozen DESIGN/MIGRATION semantics by
the implementer of the cutover slice and independently reviewed. This plan names
the required invariants, not the final queries.

## 6. Break-glass procedure

Permitted only to stop active harm: runaway or repeated writes, unexpected
cross-tenant visibility, privilege escalation, or an unrecoverable error
mid-transaction. It is **not** a way past a failed reconciliation.

1. Declare break-glass in the audit record: trigger, wall-clock time, and the
   human owner authorizing it.
2. Stop the write source at the data layer. Do **not** redeploy or restart the
   service. Withdraw the cutover row for the affected shop (`status` back to
   `locking`). Prefer the status change over deleting the row — deletion destroys
   audit evidence; if the owner chooses deletion, record both the row contents
   and the reason.
3. Prove the gate fail-closes again: an authenticated receive for that shop
   returns `503`.
4. Only if grants were changed: run the reviewed grant-rollback path, which
   restores SELECT-only while preserving the column, index, and evidence rows.
   Never widen grants under break-glass.
5. Re-snapshot Neon read-only; record counts and digest; compare with the
   phase-1 baseline.
6. Freeze further attempts, open an incident record, and do not retry inside the
   same unlock.

Break-glass never authorizes production contact, a schema change, a new role,
autodeploy, or an additional receive.

## 7. Exact stop and rollback conditions

Stop immediately — no retry inside the same unlock — on any of:

| # | Trigger | First action |
| --- | --- | --- |
| S1 | The cutover write affects more than the named shop, or creates more than one row | Stop; §6 step 2 |
| S2 | A receive for a non-cutover shop returns anything other than `503` | Stop; treat as a tenant-isolation failure; §6 |
| S3 | Any R1–R7 invariant is non-zero | Stop; do not fix forward |
| S4 | Reconciliation errors, times out, or cannot complete | Stop — timeout is not green |
| S5 | Unexpected privilege: runtime role can UPDATE/DELETE/TRUNCATE envelope tables, or any role can assume the migrator | Stop; §6 step 4 |
| S6 | Any write to a table outside the F2 envelope | Stop |
| S7 | A duplicate idempotency key produces a second row | Stop; contract violation |
| S8 | The API process restarts or crashes, or a new deployment appears during the window | Stop; autodeploy must stay off |
| S9 | Suspected credential exposure | Stop; owner rotates; record the event without printing any value |
| S10 | `/api/v1/ready` stops returning `200` with `reasons: []`, including reason `truth_migrator_role` | Stop; a migrator credential reached the app environment |
| S11 | Any phase-0 precondition cannot be evidenced | Stop before writing anything |

Rollback order — least destructive first, each verified before the next:

1. Withdraw the cutover row (`status` → `locking`) so the gate fail-closes and
   receive returns `503` again.
2. Rows already written by a receive are append-only evidence and are **not**
   deleted. Record them; reverse quantity effects only through the sanctioned
   append-only adjustment path in a separately approved slice — never by direct
   `UPDATE`/`DELETE`, which the runtime role cannot and must not be able to do.
3. Grant rollback only if grants changed; it restores SELECT-only and preserves
   the column, index, and evidence rows.
4. Schema rollback is **not** part of a staging cutover: the column and the
   partial unique index are additive and stay.
5. No redeploy, no restart, no production action, no seed.

## 8. Explicitly not authorized by this plan

- Executing cutover, inserting the row, or any successful receive.
- Any deploy or redeploy, autodeploy enablement, feature-flag or environment
  change.
- Any grant, privilege, or role change, and any use of a migrator credential.
- Any production contact, production schema apply, or data seeding.
- Any edit to frozen contract, design, migration, test, or amendment text, or to
  `GATES.md`.
- Any code change, including making `/api/v1/ready` reflect per-shop cutover.

## 9. Terminal states

| State | Meaning |
| --- | --- |
| `PREPARED — PLANNING ONLY` | initial state; nothing approved or executed |
| `OWNER DECISIONS RECORDED` | **current state** — §2 answers recorded in §2.1 as decision entry D-045; execution still not approved |
| `RUNBOOK APPROVED — READY FOR NAMED UNLOCK` | §3–§7 approved verbatim and an unlock names the shop, actor, key, and scope |
| `CUTOVER EXECUTED — RECONCILED ZERO` | one authorized cutover ran and R1–R7 returned zero variance |
| `RECORDED ON main` | evidence merged through a branch and PR |
| `REJECTED — OWNER ACTION REQUIRED` | a precondition cannot be met; the failed item and owner are named and work stops |

Timeout is never success. A rejected or stopped attempt does not start a new
planning loop.

## 10. Relationship to other records

- `CHECKPOINT-F2-CUTOVER-PLANNING.md` — the gate-level planning record this plan
  answers.
- `CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md` — endpoint deployed and verified
  fail-closed.
- `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md` — provisioning baseline and
  grant envelope.
- `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md` — where execution evidence will
  be recorded.
- `GATES-POINTER-F2-SLICE-01.md` — live gate status; frozen `GATES.md` is
  unchanged.
- `docs/agent-context/DECISIONS.md` **D-045** — the recorded owner answers to §2.
  The next state, `RUNBOOK APPROVED — READY FOR NAMED UNLOCK`, requires a
  separate named unlock; D-045 is not that unlock.
