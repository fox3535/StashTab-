# AUDIT TEMPLATE — F2 generation-1 cutover, Smoke Shop B

**Append-only.** Copy this file once per attempt to
`AUDIT-F2-CUTOVER-GEN1-<UTC-yyyymmddThhmmssZ>.md` before step 1 and fill it in
as the attempt proceeds. Never edit a completed record, never delete a line,
never rewrite a stopped attempt to look successful. A correction is a new
appended line with a wall clock and a reason, leaving the original visible.

Authority: `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §4, and D-045 decisions 1,
2, 5 and 7; supervision model D-047. Procedure: `RUNBOOK-F2-CUTOVER-GEN1.md`.

**Never record a credential, connection string, password, token, session cookie,
or URL containing any of them.** Record role **names** only. If a value must be
referenced, name where the owner holds it.

---

## A. Attempt identification

| Field | Value |
| --- | --- |
| Attempt id | `F2-CUT-GEN1-ATTEMPT-20260919T0454Z` |
| Audit file | `docs/inventory-truth-v1/AUDIT-F2-CUTOVER-GEN1-20260919T045427Z.md` (copied from the template at `9f69fde`; untracked, no commit on `main`) |
| Unlock reference (names shop, actor, key, scope) | Owner authorization of 2026-09-19: one fresh **read-only** staging preflight pinned to main `9f69fde88f971ebd767993c469d6431e92be05d7`, target `stashtab_staging`, Smoke Shop B `798d40f4-0832-46c4-991b-050e1310f6c4`, generation `1`, role `stashtab_migrator`, Path A name-only env forwarding via container `f2c`. Scope: `01-preflight.sql`, `02-baseline.sql`, `02b-baseline-notification.sql`, then stop at Gate 1. No locking INSERT, no `complete` UPDATE, no receive, no deployment, no schema or privilege change authorized. Gate 1 write authorization: **PENDING**. |
| Runbook commit (exact SHA) | `9f69fde88f971ebd767993c469d6431e92be05d7` |
| Command set commit (exact SHA) | `9f69fde88f971ebd767993c469d6431e92be05d7` — `/sql` copies in `f2c` verified 12/12 by SHA-256 against this tree |
| Target database | `stashtab_staging` |
| Target environment | staging (never production) |
| Tenant | Smoke Shop B |
| `shop_id` | `798d40f4-0832-46c4-991b-050e1310f6c4` |
| Generation | `1` |
| Reserved receive key (must stay unused) | `6f91b921-0c9d-4c75-8f54-6da9e74ef8f2` — UUIDv4, D-046 |
| Rejected control probe (H-3b, `422`/no-write) | `F2-CUT-GEN1-0001` — not a UUIDv4, D-046 |
| Notification presence state (P2 result at step 2, carried as `-v notification_baseline_state`) | **`absent`** — P2 printed `all-12-absent` in this attempt's fresh preflight on 2026-09-19 (not carried over from any earlier attempt); reused unchanged as `-v notification_baseline_state=absent` at steps 2, 5 and 7 |
| Outcome (fill last) | `COMPLETED-STOPPED-AT-STEP-8` / `STOPPED-S__` / `BREAK-GLASS` |

## B. Actors

| Role in this attempt | Identity recorded | Notes |
| --- | --- | --- |
| Owner / supervisor — Chris (authorises, present throughout) | name | |
| Automated operator — Qoder (executes the SQL under supervision) | Qoder (automated) | never an independent human reviewer |
| Supervision model (D-047 — replaces the two-person rule) | Chris supervising Qoder | two confirmation gates (§B1); silence is never approval |
| Database write role | `stashtab_migrator` | role name only, never a credential |
| Runtime role asserted | `stashtab_api` | |
| Other roles asserted | `stashtab_worker`, `stashtab_readonly` | |
| Receive actor (step 4/7 probes only) | Clerk user id | no successful receive is performed |

## B1. Supervisor confirmation gates (D-047 — replaces the two-person rule)

Qoder presents evidence and pauses; the gated write runs only after Chris's
explicit confirmation. Record the wall clock and Chris's exact confirmation. A
failed check stops execution; **silence is never approval**.

| Gate | Runs before | Qoder presented | Chris explicit confirmation (wall clock) |
| --- | --- | --- | --- |
| G-1 | step-3 generation-1 `locking` INSERT | verified target (`stashtab_staging`, Smoke Shop B, gen 1) + step-2 baseline | |
| G-2 | step-6 `complete` UPDATE | R1–R7 zero-variance results | |

## C. P0 preconditions (runbook §1) — all must be ticked before step 1

| # | Precondition | Evidenced by | Tick | Wall clock |
| --- | --- | --- | --- | --- |
| P0-1 | Named unlock recorded | unlock text | YES — Gate 1 authorized by Chris 2026-09-19: Chris supervising Qoder under Path A, Smoke Shop B `798d40f4-0832-46c4-991b-050e1310f6c4`, generation 1, `stashtab_staging`; exactly one guarded locking-row INSERT via `03-write-locking.sql`, then approved verification/reconciliation, stop at Gate 2 before any `complete` UPDATE; no successful receive authorized | 2026-09-19T06:33Z |
| P0-2 | Runbook approved verbatim; plan §3–§7 unchanged | review record | YES — runbook and operations plan exactly as merged at `9f69fde` (the owner-authorized PR #41 notification-presence correction); no change since | 2026-09-19T06:33Z |
| P0-3 | Supervision arrangement in force (Chris supervising Qoder, D-047) | §B, §B1 | YES — Chris owner/supervisor, Qoder automated operator, Path A credential transport | 2026-09-19T06:33Z |
| P0-4 | Target is `stashtab_staging`, not production | `PGDATABASE`, P-preflight G3 | YES — `g3_database = stashtab_staging` in all three files | 2026-09-19T04:54Z |
| P0-5 | Railway autodeploy off | Railway console observation | YES — project `StashTab Staging` / env `staging`: `watchPatterns: []`, `cronSchedule: []`; latest deployment `44317623-c881-4e4a-9615-984290e7dbd8` `SUCCESS`, created `2026-09-04T23:19:51.736Z`, unchanged in this window; deployed commit `ec9f72c42c4f5ad0c0adf217c05c5f766033739c` on `main`, root `services/api` | 2026-09-19T06:31Z |
| P0-6 | No worker, no cron | log window | YES — the environment holds exactly one service instance (`api`), `cronSchedule: []`, and `/api/v1/ready` reports `features.worker = false`, `features.notifications_backend = false` | 2026-09-19T06:31Z |
| P0-7 | Exactly one API process | direct in-container inspection (`/proc`) | **YES — VERIFIED by direct read-only inspection at `2026-09-19T20:26:02Z`** via temporary SSH (Railway's supported mechanism: dedicated temporary personal key `f2c-temp-inspect-20260919` registered, used once, then `railway ssh keys remove`d and local key material deleted; no workspace-admin, no app/env/deploy change). Container/instance identity `hostname 6a36782dfca7`. `/proc` enumeration computed each process's wall-clock start from `starttime` (field 22) + host `btime` at `HZ=100` — **`/proc/uptime` deliberately NOT used** (shared host kernel). Result `TOTAL_PROCS=3`, of which exactly **one** is the API: **PID 1 (PPID 0), comm `uvicorn`, cmdline `/usr/local/bin/python3.12 /usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080`, start `2026-09-04T23:20:45Z`, elapsed `1,285,516s` (~14.9 d), PRE_FREEZE=YES**. The other two are this inspection's own transient processes (PID 62 `bash -c echo…`, PID 65 `python3 -`, both start `20:26:01Z`), NOT API processes — so total process count is not equated with API process count. No uvicorn `--workers`/`--reload` children, no worker process, no cron process. The single API process's start precedes the freeze-window start `2026-09-19T04:54:27Z` by ~15 days with continuous elapsed time → **no restart during the window**; cross-validated by deployment `44317623` `createdAt 2026-09-04T23:19:51Z` (+~54 s). Metrics (deployment list; CPU/mem continuity) are retained as supporting context only, not as the proof. Residual uncertainty: the 2026-09-19 snapshot proved continuity only up to `20:26:02Z`. **Re-verified `2026-09-21T00:48:12Z`** (after the Docker-outage and laptop-restart interruptions) by the same temporary-SSH `/proc` method (dedicated key `f2c-s8-temp-20260920` registered, used once, then removed — registry verified empty; local keypair, temp `known_hosts`, and scratch deleted; `~/.ssh` restored to non-existent): instance `hostname 6a36782dfca7` and host `btime 1781869087` unchanged; `API_PROC_COUNT=1`; **PID 1 (PPID 0) `uvicorn app.main:app --host 0.0.0.0 --port 8080`, start `2026-09-04T23:20:45Z`, MATCHES_RECORDED=YES, PRE_FREEZE=YES, elapsed `1,387,646s` (~16.06 d)** — the same single process continuously running, so no API restart between the recorded baseline and now; the only other pids were the inspection's own transient bash/python3. This closes the gap Chris raised: an unchanged deployment id proves no redeploy but NOT no restart, whereas the matching process start time proves no restart directly. The runbook still re-checks at step 7 | 2026-09-21T00:48Z |
| P0-8 | No open incident | incident tracker | YES — no incident tracker exists in the repository, so this was not self-evidenced; asked Chris one plain question, and Chris confirmed 2026-09-19 "not aware of any open incident affecting stashtab_staging" | 2026-09-19T06:33Z |
| P0-9 | `inventory_truth_cutover` empty | `01-preflight.sql` P7 | YES — `p7_cutover_empty = zero-rows-globally`; `02-baseline.sql` B3 `cutover_rows = 0` | 2026-09-19T04:54Z |
| P0-10 | Audit file created and open | this file | YES — created from the template at `9f69fde`, left untracked; no commit on `main` | 2026-09-19T06:33Z |

Any unticked line is **S11**: stop before writing anything.

State at 2026-09-21T00:48Z: all ten P0 preconditions remain evidenced YES; P0-7/S8 (exactly one API process, no restart) was re-verified by direct in-container inspection after the Docker-outage and laptop-restart interruptions — the same single `uvicorn` PID 1, start `2026-09-04T23:20:45Z` (MATCHES_RECORDED=YES), elapsed ~16.06 d, so no restart during the window. P0-7 was originally closed by
**direct read-only in-container inspection** (not metrics inference): exactly one API process
(`uvicorn app.main:app`, PID 1) whose start `2026-09-04T23:20:45Z` precedes the freeze-window
start `2026-09-19T04:54:27Z` with continuous elapsed time, so no restart during the window and
no worker/cron process. Temporary SSH access was created solely for this inspection and fully
removed afterward (the temporary Railway keys `f2c-temp-inspect-20260919` and `f2c-s8-temp-20260920` were each unregistered after use — registry verified empty; local keypairs, temp
`known_hosts`, and scratch files deleted; `~/.ssh` restored to its prior non-existent state).
As of the 2026-09-21T00:48Z P0 re-verification, no deployment, restart, app-config change, database
write, or cutover had occurred. Step 3's single guarded locking INSERT was subsequently EXECUTED by Chris at `2026-09-21 00:58:16.503535+00` (`COMMIT`, `EXIT=0`): one generation-1 `locking` row (`id=1`, Smoke Shop B, `opened_at` NULL); no `complete` UPDATE. Gate 2 and receive remain locked. See §D step 3.
Prior stopped attempts are preserved separately and are not part of this record:
`CHECKPOINT-F2-G5-OWNER-EXCEPTION.md` (S5) and `CHECKPOINT-F2-P2-STOP.md` (S11).

## D. Step log — append one row per step, in order

| Step | File / probe | Wall clock start | Wall clock end | psql exit | Tokens / values observed | Actor |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | session open + `ready` | <Chris to fill: private session open> | <Chris to fill> | n/a | `current_user` = `session_user` = `stashtab_migrator` (G9); `current_database()` = `stashtab_staging` (G3); `version()` = PostgreSQL 16.15 (eb11870) (P8); `/api/v1/ready` `200` `"reasons": []`, `inventory_cutover: false`, `dev_bypass_allowed: false`, `database.connected: true`; `/api/v1/health` `200` | Chris (credential entry) + Qoder (operator) |
| 2 | `01-preflight.sql` | <Chris to fill; before 04:54:27Z> | <Chris to fill> | 0 | G1 `798d40f4-0832-46c4-991b-050e1310f6c4`; G1b `shop-id-double-entry-agrees`; G2 `1`; G3 `stashtab_staging`; G4 `stashtab_migrator,stashtab_api`; G5 `no-unapproved-role-can-assume-stashtab_migrator`; G6 `no-superuser`; G7 `2/2`; G8 `shop-present-with-one-membership`; G9 `stashtab_migrator`; P1 `all-13-present`; **P2 `all-12-absent`** (→ §A); P3 `varchar(36)-nullable`; P4 `unique-partial-two-column`; P5 `select-only`; P6 `select-insert-update`; P7 `zero-rows-globally`; P8 `postgresql-16.15 (eb11870)` | Qoder via `f2c`, Chris's session |
| 2 | `02-baseline.sql` | 2026-09-19 04:54:27.776376+00 (B0) | <Chris to fill> | 0 | B0 `freeze_window_start = 2026-09-19 04:54:27.776376+00`, `session_time_zone = GMT`; B1 13 rows (→ §E); B2 `r5_inventory_digest = 8669a4d11ff3bc75cb3b7b737236c9f7`; B3 `inventory_item 0 / purchase_record 0 / acquisition_lot 0 / inventory_event 0 / cutover_rows 0`; B4 `shops 2`, `shop_members 2`, `api_item_select t`, `api_item_insert t`, `api_item_update_wide f`, `api_item_update_stock t`, `api_item_update_cost t`, `api_item_delete f`, `api_item_truncate f` | Qoder via `f2c`, Chris's session |
| 2 | `02b-baseline-notification.sql` | <Chris to fill; after 04:54:27Z> | <Chris to fill> | 0 | `n0p_notification_presence_state = baseline-state-absent`; absent branch: `r5_notification_digest = 75e7e3d7093ac362292ab59fe82b7321` (= `md5('notification-relations-absent')`, matches the value computed locally), `n1_absent_baseline = notification-relations-absent-baseline`; no per-relation N1 rows; run with `-v notification_baseline_state=absent` | Qoder via `f2c`, Chris's session |
| 3 | `03-write-locking.sql` | 2026-09-21 00:58:16.503535+00 (frozen_at/created_at) — EXECUTED by Chris in his private session | 2026-09-21 (COMMIT) | 0 | **History:** 2026-09-19 BLOCKED (Docker engine down, `f2c` absent). 2026-09-20 Path A RESTORED: existing `f2c` (postgres:16) already `Up` (auto-restarted, NOT recreated); unrelated containers preserved (`stashtab-f2cut-bee09da4`, `stashtab-pg-accept`, `mimir-redis`, `mimir-postgres`); 12/12 `/sql` hashes re-verified vs clean `9f69fde` (no mismatch/extra). After a further laptop restart, re-verified HEAD `9f69fde`, `f2c` `Up`, 12/12 hashes, `01-preflight.sql` container==tree `d7cc08ab…`. **Pre-write rechecks COMPLETE (2026-09-20):** (a) DB-side read-only `01-preflight.sql` re-run in Chris's restored `stashtab_migrator`/`stashtab_staging` session — **EXIT=0**, every token identical to the recorded baseline: G1 `798d40f4…`, G1b agrees, G2 `1`, G3 `stashtab_staging`, G4 `stashtab_migrator,stashtab_api`, G5 no-assumption, G6 no-superuser, G7 `2/2`, G8 shop-present-one-membership, G9 `stashtab_migrator`, P1 `all-13-present`, **P2 `all-12-absent` (S11 notification presence unchanged)**, P3 `varchar(36)-nullable`, P4 `unique-partial-two-column`, P5 `select-only`, P6 `select-insert-update`, **P7 `zero-rows-globally`**, P8 `postgresql-16.15 (eb11870)`. (b) Railway no-redeploy recheck — live deployment still `44317623` SUCCESS (created 2026-09-04T23:19:51Z), no new deployment in window; `/api/v1/ready` `200` (`reasons:[]`, `inventory_cutover:false`, `worker:false`). **CORRECTION (Chris, 2026-09-21): an unchanged deployment id proves NO NEW DEPLOYMENT only, NOT no API restart.** The no-restart property was therefore re-verified directly by temporary-SSH `/proc` inspection at `2026-09-21T00:48:12Z` — same instance `hostname 6a36782dfca7` / host `btime 1781869087`, `API_PROC_COUNT=1`, PID 1 `uvicorn app.main:app` start `2026-09-04T23:20:45Z` MATCHES_RECORDED=YES, elapsed `1,387,646s` (~16.06 d), so no restart (see P0-7); temp key `f2c-s8-temp-20260920` removed, registry empty, local key material + `~/.ssh` deleted. `freeze_window_start` audit-record-only (runbook L303); drift caught fail-closed at step 5. **Write authorized:** Gate 1 carried forward; single `03-write-locking.sql` INSERT (Smoke Shop B, gen 1, `stashtab_staging`, full 9-var `$F2`, guards G1–G9 + W0/W0b/W2/W3 intact, no `notification_baseline_state`; local SHA256 `a4e1c0aa…`) provided to Chris, then **EXECUTED 2026-09-21 in his private session: `COMMIT`, `EXIT=0`**. Returned W4 evidence: **row `id=1`, `shop_id=798d40f4-0832-46c4-991b-050e1310f6c4` (Smoke Shop B), `generation=1`, `status=locking`, `frozen_at`=`created_at`=`2026-09-21 00:58:16.503535+00`, `opened_at=NULL`** — exactly one generation-1 `locking` row, no `complete`, no second row; INSERT not rerun. Proceeding to step-4 verification/reconciliation one command at a time. **Gate 2 (`complete` UPDATE) and receive remain locked.** | Qoder (operator) / Chris (executed) |
| 4 | `04-verify-locking.sql` | 2026-09-21 (after locking commit) | 2026-09-21 | 0 | G1–G9 pass (as step 2); **V1 `one-row-globally`**, **V2 `pinned-shop-gen1-only`**, **V3 `locking-with-frozen_at-and-no-opened_at`**, **V4 `gate-reads-locking`** (gate fail-closes → receive `503`), V5 row `id=1` / `798d40f4-0832-46c4-991b-050e1310f6c4` / gen `1` / `locking` / `frozen_at`=`created_at`=`2026-09-21 00:58:16.503535+00` / `opened_at` NULL, **V6 `no-receive-evidence`**, **V7 `reserved-and-probe-keys-unused`**; `EXIT=0` | Qoder via `f2c`, Chris's session |
| 4 | H-1, H-2, H-3, H-3b, H-4 | 2026-09-21T01:08:46Z (H-1, H-4) | 2026-09-21 | n/a | **H-1 `401`** ✓ (unauth, fail-closed before gate/write), **H-4 `200`/`reasons:[]`** ✓ (`inventory_cutover:false`) — both credential-free, operator-run (→ §G). **H-2/H-3/H-3b PENDING** — require a Clerk member token (`$TOKEN`) held privately by Chris: H-2 + H-3b use the Smoke Shop B member token, H-3 uses a *different* shop's member token (tenant isolation); run one at a time in his session. Any `2xx` from receive → immediate stop (S2). | Qoder (H-1/H-4) / Chris (H-2/H-3/H-3b) |
| 5 | `05-r1-r7.sql` | 2026-09-25 (resumption, Chris's private session via corrected full-variable `docker exec` invocation) | 2026-09-25 | 0 | all §6 tokens printed and verified by exact equality (→ §H): G10 `baseline-digest-present`, G11 `15000/5000`, G12 `stashtab_worker,stashtab_readonly`, `evaluating-at-locking`, `R1-zero`, `overlay-deltas-are-zero`, `one-stock-row-per-sku`, `R2-zero`, `R3-zero`, `replay-rows-added-0`, `R4-zero`, `R5a-unchanged`, R5b pointer `R5b-deferred-to-05b-r5-notification.sql`, `R5c-envelope-empty`, `R6-zero`, `R7a-zero`…`R7e-zero`, gate summary 7 rows, `COMMIT`, `EXIT=0`. R1e/R2c context: all examined-row counts 0 → trivial zeros over 0 rows | Qoder (command) / Chris (execution) |
| 5 | `05b-r5-notification.sql` | 2026-09-25 (resumption, Chris's private session, corrected full-variable invocation) | 2026-09-25 | 0 | G1–G9 green; G15 `notification-baseline-present`; G16 `15000`; READ ONLY transaction (`BEGIN`/`SET`×2/`COMMIT`); `nb0p_notification_presence_state = baseline-state-absent` (equals §A); `nb1_evaluation_point = evaluating-at-locking`; `r5b_result = R5b-notification-relations-still-absent`; `r5b_pinned_shop_rows = R5b-zero-rows-for-pinned-shop-absent-relations`; no `present`-set token, no `*_partial_presence`, no state-change parameter; `EXIT=0` → **step 5 COMPLETE** (both files green) | Qoder (command) / Chris (execution) |
| 6 | `06-write-complete.sql` | | | | T0, T0b, T0c, T1–T4 + row (→ §F) | |
| 7 | `07-final-verification.sql` | | | | F1–F9 (→ §H) | |
| 7 | `07b-verify-notification.sql` | | | | `nb0pv_notification_presence_state`, F10, F11 — the §H step-7 pair **for the state recorded in §A** | |
| 7 | H-3, H-4 | | | n/a | statuses (→ §G) | |
| 8 | stop + credential destroyed | | | n/a | see §K | |

## E. Hashes and digests

Copy the exact 32-character values printed. Do not retype them from memory. A
transcription error is caught later by a digest mismatch, which is the intended
behaviour.

| Name | Source | Value |
| --- | --- | --- |
| `baseline_digest` (13 relations, incl. cutover) | `02-baseline.sql` | `4a556fc25312fc7c9664f80f84c9f271` |
| `baseline_excl_cutover` (12 relations) | `02-baseline.sql` | `058e9f26376fa7e7c95bfc6afdf452e8` |
| `base_r5_inventory` (6 out-of-envelope) | `02-baseline.sql` | `8669a4d11ff3bc75cb3b7b737236c9f7` |
| `base_r5_notification` (12 notification relations; when all 12 are absent this is the absence marker `md5('notification-relations-absent')`) | `02b-baseline-notification.sql` | `75e7e3d7093ac362292ab59fe82b7321` — absence marker (§A state `absent`) |
| `n0p_notification_presence_state` | `02b-baseline-notification.sql` N0p | `baseline-state-absent` |
| `freeze_window_start` | `02-baseline.sql` B0 | `2026-09-19 04:54:27.776376+00` (GMT) |
| `freeze_window_end` | `07-final-verification.sql` F0 | pending — step 7 not run |
| `bg_pre_digest` (only if break-glass ran) | `08-break-glass-locking.sql` BG1 | n/a — break-glass not run |

Per-relation baseline rows (total / pinned-shop) — paste the full aligned output
of `02-baseline.sql` B1 below. Add `02b-baseline-notification.sql` N1 when the
§A state is `present`. When the §A state is `absent`, N1 prints no per-relation
rows: paste its two columns instead (`r5_notification_digest` = the absence
marker, `n1_absent_baseline` = `notification-relations-absent-baseline`) and
annotate the block `N1-not-applicable-relations-absent`. Never leave this block
empty, and never paste a present-state N1 table for an `absent` attempt:

```text
B1 (02-baseline.sql), verbatim:
              rel              | total_rows | cutover_shop_rows |         baseline_digest          |      baseline_excl_cutover
-------------------------------+------------+-------------------+----------------------------------+----------------------------------
 acquisition_lot               |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 inventory_adjustment          |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 inventory_channel_observation |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 inventory_event               |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 inventory_exception           |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 inventory_item                |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 inventory_truth_cutover       |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 purchase_record               |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 refund_record                 |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 return_record                 |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 sale                          |          0 |                 0 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 shop_members                  |          2 |                 1 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
 shops                         |          2 |                 1 | 4a556fc25312fc7c9664f80f84c9f271 | 058e9f26376fa7e7c95bfc6afdf452e8
(13 rows)

N1-not-applicable-relations-absent
02b-baseline-notification.sql absent branch, verbatim:
      r5_notification_digest      |           n1_absent_baseline
----------------------------------+----------------------------------------
 75e7e3d7093ac362292ab59fe82b7321 | notification-relations-absent-baseline
(1 row)
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
| H-1 | 2026-09-21T01:08:46Z | `/api/v1/admin/inventory/receive` | Smoke Shop B | no | fresh UUIDv4 `8c7e98d2…af49` | **`401`** (expect `401`) ✓ | `{"detail":"Authenticated user required"}` — no `error`/`feature`; rejected at `get_shop_context` (auth) before the gate/write | access log `100.64.0.16:41426 "POST /api/v1/admin/inventory/receive" 401 Unauthorized` (no separate request-id field emitted) |
| H-2 | 2026-09-24 (resumption) | same | Smoke Shop B | yes (Chris's Clerk member token, obtained in-page via `window.Clerk.session.getToken()` in the signed-in local browser at `localhost:3001`; token never printed/stored) | fresh UUIDv4 `6871221f-57ae-4e6a-b251-f9da71e76f9b` | **`503`** (expect `503`) ✓ | `{"error":"FEATURE_NOT_READY","feature":"inventory_truth","message":"This operation is not enabled in this environment."}` — gate fail-closed while `locking`; membership pre-verified via `GET /api/v1/shops/me/memberships` → `200`, single membership: Smoke Shop B, role `owner` | not captured in this run |
| H-3 | 2026-09-24 (resumption) | same | Smoke Shop A (`299c7a35-9ee0-45d4-989e-daf1bbcdc913`) | yes (that shop's member token — Chris's own Chrome session, in-page `getToken()`, never printed; membership pre-verified `200`/`owner`) | fresh UUIDv4 `2290870c-7ea7-4888-8c4d-d268bae05699` | **`503`** (expect `503`) ✓ | `{"error":"FEATURE_NOT_READY","feature":"inventory_truth","message":"This operation is not enabled in this environment."}` — gate fail-closed for the non-pinned shop; tenant isolation intact, no 2xx | browser console line `POST …/receive 503 (Service Unavailable)`; Railway request id not captured |
| H-3b | 2026-09-24 (resumption) | same | Smoke Shop B | yes (same in-page Clerk token method as H-2; never printed/stored) | `F2-CUT-GEN1-0001` (not a UUIDv4) | **`422`** (expect `422`) ✓ | `{"detail":"Idempotency-Key must be a UUIDv4 (36 chars)"}` — key validation precedes the gate; proves the `422` class cannot mask a gate result; no write (V7/F8 marker check covers `F2-CUT-GEN1-0001`) | not captured in this run |
| H-4 | 2026-09-21T01:08:46Z | `/api/v1/ready` | n/a | n/a | n/a | **`200`**, `reasons: []` ✓ | `status:ready`, `app_env:staging`, `database.connected:true`, `schema.inventory_truth:true`/`notifications:false`, `features.inventory_cutover:false`/`worker:false` | access log `"GET /api/v1/ready" 200 OK` |
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

Token matching is **exact string equality against the printed column value**,
never substring containment: `R5b-unchanged-at-step-7-absent-relations` does not
satisfy a requirement for `R5b-unchanged-at-step-7`. Record only the row that
matches the notification presence state in §A. A mixed present/absent token set
is a failure, and so is any `*_partial_presence` or
`*_presence_changed_during_attempt` stop parameter. Partial presence (1 to 11 of
the twelve relations) is never recorded as a pass and is never provisioned,
repaired or dropped by the operator.

| # | Invariant | Token required | Observed | Notes |
| --- | --- | --- | --- | --- |
| R1 | snapshot vs append-only truth | `R1-zero` | **`R1-zero`** ✓ | R1a empty; R1e: 0 snapshot rows, 0 event rows, sums 0/0 → **trivial** zero over 0 rows |
| R1c | overlay events carry `quantity_delta = 0` | `overlay-deltas-are-zero` | **`overlay-deltas-are-zero`** ✓ | `ck_overlay_zero_delta` CHECK definition printed as it exists on this database |
| R1d | `uq_inventory_shop_sku` present | `one-stock-row-per-sku` | **`one-stock-row-per-sku`** ✓ | |
| R2 | receive envelope completeness | `R2-zero` | **`R2-zero`** ✓; `r2_rows_examined = 0` → **trivial** zero over 0 rows | R2a empty; lot/event rows for shop 0/0 |
| R3 | idempotency uniqueness | `R3-zero` | **`R3-zero`** ✓ | **trivial** zero; R3b `replay-rows-added-0` — reserved/probe keys produced 0 rows |
| R4 | cutover row discipline at `locking` | `R4-zero` | **`R4-zero`** ✓ | |
| R5a | out-of-envelope inventory digest | `R5a-unchanged` | **`R5a-unchanged`** ✓ | digest equals step-2 B2 `8669a4d1…c9f7` |
| R5b — §A state `present` | all 12 notification relations exist and are unchanged | `R5b-unchanged` + `R5b-zero-rows-for-pinned-shop` | from `05b` | NOT the §A state — row not applicable (§A = `absent`) |
| R5b — §A state `absent` | all 12 notification relations are still absent | `R5b-notification-relations-still-absent` + `R5b-zero-rows-for-pinned-shop-absent-relations` | **both ✓** from `05b` (2026-09-25, `EXIT=0`) | §A state `absent` honored; no mixed tokens |
| R5c | envelope empty for pinned shop | `R5c-envelope-empty` | **`R5c-envelope-empty`** ✓ | |
| R6 | identity invariance | `R6-zero` | **`R6-zero`** ✓ | `shops = 2`, `shop_members = 2`, one membership for pinned shop |
| R7a | envelope table grants | `R7a-zero` | **`R7a-zero`** ✓ | |
| R7b | USAGE on the four F2 sequences | `R7b-zero` | **`R7b-zero`** ✓ | |
| R7c | PUBLIC holds nothing | `R7c-zero` | **`R7c-zero`** ✓ | |
| R7d | worker/readonly hold nothing | `R7d-zero` | **`R7d-zero`** ✓ | |
| R7e | cutover write path | `R7e-zero` | **`R7e-zero`** ✓ | |
| — | evaluation point | `gate_evaluation_point = evaluating-at-locking` | **`evaluating-at-locking`** ✓ | |
| — | notification evaluation point | `nb1_evaluation_point = evaluating-at-locking` | **`evaluating-at-locking`** ✓ | |
| — | notification presence state at step 5 | `nb0p_notification_presence_state = baseline-state-absent` or `baseline-state-present` (must equal §A) | **`baseline-state-absent`** ✓ (equals §A `absent`) | |

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
| F10 notification digest at step 7 — §A state `present` | `R5b-unchanged-at-step-7` | |
| F10 notification relations still absent at step 7 — §A state `absent` | `R5b-unchanged-at-step-7-absent-relations` | |
| F11 zero notification rows, pinned shop — §A state `present` | `R5b-zero-rows-for-pinned-shop` | |
| F11 zero notification rows, pinned shop — §A state `absent` | `R5b-zero-rows-for-pinned-shop-absent-relations` | |
| NB0pv notification presence state at step 7 | `nb0pv_notification_presence_state = baseline-state-absent` or `baseline-state-present` (must equal §A) | |
| F12 per-relation detail (printed by `07b` in the `present` state only) | the aligned `rel` / `cutover_shop_rows` table, or `F12-not-applicable-relations-absent` | |

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
| `F2-CUT-GEN1-0001` used | must be `NO` — H-3b control probe only; must return `422` and write nothing (D-046) |
| Reserved UUIDv4 `6f91b921-0c9d-4c75-8f54-6da9e74ef8f2` used | must be `NO` — reserved for the later first-receive proof (D-046) |
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

## N. Resumption log — 2026-09-24 (owner-authorized resumption; Gate 2 and receive remain locked)

Append-only continuation. Baselines above are preserved unchanged.

| Wall clock (UTC) | Actor | Check | Evidence |
| --- | --- | --- | --- |
| 2026-09-24T07:30Z | Qoder | Resumption check 1 — repo + SQL integrity | local HEAD `e8fb3b2` (main after PR #42, matches owner checkpoint); 12/12 `scripts/f2-cutover/sql/*.sql` SHA-256 equal to the audit-recorded set (`01` = `d7cc08ab1840…`) and equal to `/sql` copies inside `f2c` (12/12 match) |
| 2026-09-24T07:35Z | Qoder | Resumption check 2 — vehicle + credential model | `f2c` (postgres:16) Up; container env carries no PG* connection variables (names enumerated: image defaults only), so credentials remain solely in Chris's private session; unrelated container `stashtab-f2cut-bee09da4` (Created, never started) left untouched |
| 2026-09-24T07:36Z | Qoder | Resumption check 3 — deployment + readiness | deployment ID `44317623-c881-4e4a-9615-984290e7dbd8` unchanged (proves no-redeploy only); `GET /api/v1/ready` → 200 `{reasons: [], features.inventory_cutover: false, schema.inventory_truth: true, schema.notifications: false}` matching the H-4 baseline |
| 2026-09-24T07:38:10Z | Qoder | Resumption check 3b — process continuity (authorized temporary read-only SSH, full cleanup) | snapshot hostname `6a36782dfca7`, `API_PROC_COUNT=1`, PID 1 `/usr/local/bin/python3.12 /usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --p…`, `START_UTC 2026-09-04T23:20:45Z`, `MATCHES_RECORDED=YES` vs recorded baseline → same continuously running process, no restart since 2026-09-04 |
| 2026-09-24T07:40Z | Qoder | Cleanup verification | `railway ssh keys remove SHA256:T5P6SX9t…` succeeded; `railway ssh keys list` → "No SSH keys registered with Railway"; `~/.ssh` restored to non-existent; temp known_hosts and `.git\f2c_s8_inspect2.py` scratch deleted; worktree untracked set unchanged (12 lines, F2 artifacts intact) |
| 2026-09-24T07:41Z | Qoder | Resumption check 4 — locking row re-verification | PENDING: `04-verify-locking.sql` (read-only, idempotent) to be executed by Chris in his private PG session; V1–V7 expected green; `01-preflight` NOT rerun (requires empty table), `03-write-locking` never rerun |
| 2026-09-24T08:05Z | Chris (private session) → Qoder | Resumption check 4 RESULT — `04-verify-locking.sql` rerun | G1–G9 green (`g9_session_role=stashtab_migrator`, `g8 shop-present-with-one-membership`, `g7 2/2`), V1 `one-row-globally`, V2 `pinned-shop-gen1-only`, V3 `locking-with-frozen_at-and-no-opened_at`, V4 `gate-reads-locking`, V5 row id=1 shop `798d40f4-0832-46c4-991b-050e1310f6c4` gen 1 `locking` frozen_at/created_at `2026-09-21 00:58:16.503535+00` opened_at NULL (byte-identical to baseline), V6 `no-receive-evidence`, V7 `reserved-and-probe-keys-unused`, `EXIT=0`. Locking re-verified; no drift; baselines preserved |
| 2026-09-24T07:41Z | Qoder | Outstanding approved checks | H-2 (Smoke Shop B authenticated receive while locking → expect 503), H-3 (other shop → 503), H-3b (422 no-write control), then R1–R7 via `05`+`05b` with step-2 baselines and `notification_baseline_state=absent`; stop at Gate 2 before any `06-write-complete.sql` |
| 2026-09-24T08:15Z | Qoder (Browser subagent, Chris signed in) | H-2 executed — authenticated receive while `locking` | Membership verified first: `GET /api/v1/shops/me/memberships` → `200`, exactly one membership `{id: 798d40f4-0832-46c4-991b-050e1310f6c4, name: Smoke Shop B, role: owner}`. Then `POST /api/v1/admin/inventory/receive` with fresh in-page UUIDv4 `6871221f-57ae-4e6a-b251-f9da71e76f9b`, probe body `sku=F2-PROBE-DO-NOT-USE` → **`503`** `{"error":"FEATURE_NOT_READY","feature":"inventory_truth"}` — expected fail-closed; no 2xx; token never left the page context (Clerk `getToken()` in-page only) |
| 2026-09-24T08:20Z | Qoder (Browser subagent, same session) | H-3b executed — control probe | `POST /api/v1/admin/inventory/receive` with `Idempotency-Key: F2-CUT-GEN1-0001` (non-UUIDv4) → **`422`** `{"detail":"Idempotency-Key must be a UUIDv4 (36 chars)"}` — rejected before the gate, exactly as specified (D-046 control); single request, no retries, token hygiene confirmed |
| 2026-09-24T08:22Z | Qoder | H-3 blocker — other-shop member token unavailable | H-3 requires *that shop's* member token (runbook §5). Chris's verified membership list contains exactly one shop (Smoke Shop B, `owner`), so the signed-in session cannot produce a second-shop member token. Awaiting owner decision: provide/sign in a member of the other staging shop, or record H-3 as not executable this attempt. No substitute probe run (wrong-shop `X-Shop-Id` with the Smoke Shop B token would fail at membership resolution, not at the gate, and would not satisfy the H-3 spec) |
| 2026-09-24T08:35Z | Qoder | H-3 HELD — other-shop membership verification via Chris's own Chrome | Owner directs: Chris is signed in with the other staging shop account in regular Chrome (not the automated browser). Qoder supplied one read-only console snippet for `localhost:3001` that uses the in-page Clerk session to call `GET /api/v1/shops/me/memberships` and prints only HTTP status + `{id,name,role}` per shop — token never printed, no credentials copied between browsers, no membership changes, no auth bypass. H-3 will only be issued after the returned response confirms the other shop and an `owner`/`staff` role. Gate 2 remains locked |
| 2026-09-24T08:50Z | Chris (own Chrome) → Qoder | H-3 membership verification RESULT | `GET /api/v1/shops/me/memberships` → `200`; single membership: **Smoke Shop A**, id `299c7a35-9ee0-45d4-989e-daf1bbcdc913`, role `owner` — confirms the other-shop member token requirement (runbook §5 H-3); distinct from pinned Smoke Shop B `798d40f4-0832-46c4-991b-050e1310f6c4`. Hold condition satisfied; Qoder handed Chris the single approved H-3 probe snippet (approved `probe-body.json` payload, fresh in-page `crypto.randomUUID()` key — NOT the reserved `6f91b921-…`, token in-page only, prints status/key/body). Expected `503` `FEATURE_NOT_READY`/`inventory_truth`; any `2xx` → stop; unexpected result → report without retry. Gate 2 remains locked |
| 2026-09-24T09:05Z | Chris (own Chrome) → Qoder | H-3 executed — RESULT | Console output: `H3_STATUS=503`, `H3_KEY=2290870c-7ea7-4888-8c4d-d268bae05699` (fresh UUIDv4, reserved key unused), `H3_BODY={"error":"FEATURE_NOT_READY","feature":"inventory_truth","message":"This operation is not enabled in this environment."}` — expected fail-closed for the other shop; single run, no retries, token never printed. All outstanding HTTP checks for step 4 now complete: H-1 `401`, H-2 `503`, H-3 `503`, H-3b `422`, H-4 `200` |
| 2026-09-24T09:20Z | Chris (owner correction) → Qoder | Step-5 invocation corrected before execution | Owner correction: do not assume the abbreviated `05` command sufficient. Qoder re-read `05-r1-r7.sql` (line 35 `\ir lib-guards.sql`; header lists `base_r5_inventory`, `recon_timeout_ms`, `lock_timeout_ms`, `worker_role`, `readonly_role`) and `lib-guards.sql` (requires the full nine-variable `$F2` block per runbook lines 207–217: `cutover_shop_id`, `pinned_shop_id`, `cutover_generation`, `write_role`, `read_role`, `expected_database`, `expected_role`, `expected_shops`, `expected_shop_members`). The previously drafted abbreviated `05` command omitted the `$F2` block and would have fail-closed (unset psql variable → syntax error under ON_ERROR_STOP); it was NOT executed. Corrected complete `05` command handed to Chris: name-only env forwarding `-e PGHOST -e PGPORT -e PGDATABASE -e PGUSER -e PGPASSWORD -e PGSSLMODE` (no credential values expanded into arguments), `psql -X -w -v ON_ERROR_STOP=1`, full `$F2` block, `base_r5_inventory=8669a4d11ff3bc75cb3b7b737236c9f7` (recorded step-2 B2 digest), `recon_timeout_ms=15000`, `lock_timeout_ms=5000`, `worker_role=stashtab_worker`, `readonly_role=stashtab_readonly`, `-f /sql/05-r1-r7.sql`. `05b` (with `base_r5_notification=75e7e3d7093ac362292ab59fe82b7321`, `notification_baseline_state=absent`) will be issued only after `05` returns full output with `EXIT=0` and every §6 token verified; any failure stops, no automatic retry. No new database operation authorized by this correction; Gate 2 remains locked |
| 2026-09-25T09:30Z | Chris (private session) → Qoder | Step 5 first half — `05-r1-r7.sql` RESULT: PASS | One earlier paste was the `04` output again (identified, not recorded as step 5; operator re-ran the correct file). Full corrected invocation output: G1–G9 green; G10 `baseline-digest-present`; G11 `15000/5000`; G12 `stashtab_worker,stashtab_readonly`; READ ONLY transaction (`BEGIN`/`SET`×3/`COMMIT`); `gate_evaluation_point = evaluating-at-locking`; R1a empty, R1c `overlay-deltas-are-zero` + printed CHECK definition, R1d `one-stock-row-per-sku`, R1b `R1-zero`, R1e all counts 0; R2a empty, R2b `R2-zero`, R2c `r2_rows_examined=0`; R3a `R3-zero`, R3b `replay-rows-added-0`; R4 `R4-zero`; R5a `R5a-unchanged`; R5b pointer printed; R5c `R5c-envelope-empty`; R6 `R6-zero`; R7a–R7e `R7a-zero`…`R7e-zero`; gate summary 7 rows; `EXIT=0`. All §6 tokens verified by exact equality; R1–R3 recorded as trivial zeros over 0 rows (D-045 decision 4, not receive proofs). §D step-5 row and §H table filled. Step 5 NOT complete until `05b` prints zero (partial reconciliation = failure, D-045 decision 6); `05b` command issued to Chris (full `$F2` block + `base_r5_notification=75e7e3d7093ac362292ab59fe82b7321` + `notification_baseline_state=absent` + `recon_timeout_ms=15000`; no `lock_timeout_ms` — file sets only `statement_timeout`). Gate 2 remains locked |
| 2026-09-25T10:00Z | Chris (private session) → Qoder | Step 5 second half — `05b-r5-notification.sql` RESULT: PASS → STEP 5 COMPLETE | Output matched the `05b`-specific token set: G1–G9 green; G15 `notification-baseline-present`; G16 `15000`; READ ONLY (`BEGIN`/`SET`×2/`COMMIT`); `nb0p_notification_presence_state = baseline-state-absent` (equals §A); `nb1_evaluation_point = evaluating-at-locking`; `r5b_result = R5b-notification-relations-still-absent`; `r5b_pinned_shop_rows = R5b-zero-rows-for-pinned-shop-absent-relations`; no present-set token, no `*_partial_presence`; `EXIT=0`. Recorded in §D step-5 `05b` row and §H (R5b absent row, nb1, nb0p). R1–R7 zero variance while `locking`. **STOPPED AT GATE 2** — `06-write-complete.sql` not issued, not run; row remains `locking`; no approval assumed |
| 2026-09-29 | Qoder (desktop) | Desktop handoff — repository inspection and sync (owner-authorized; no staging/DB/credential operations) | Desktop repo `c:\Users\Chris\Desktop\Cursor Projects\StashTab`, remote `origin https://github.com/fox3535/StashTab-.git`; branch `main` at `e8fb3b2ae1bb5833a56d661b2cf0ae52fa96cbc8` (PR #42 merge) — after `git fetch origin`, `origin/main` is the same commit: up to date, nothing to fast-forward, no reset/clean/stash performed; zero tracked modifications; untracked set preserved intact (12 entries incl. this audit, `.qoder/`, `lib/use-api-auth.ts`, barcode PNGs, `mobile-header-screenshot.png`, `scripts/f2-cutover/__pycache__/`). Audit availability: this file present (47,549 bytes, last written 2026-09-25T01:07 local) and content-current through the step-5 records above (§D rows for `05`/`05b` filled, §H table complete, §N log through 2026-09-25); prior stop records present: `CHECKPOINT-F2-P2-STOP.md` and `CHECKPOINT-F2-G5-OWNER-EXCEPTION.md`. Gate 2: submission/execution of any approval remains UNCONFIRMED — §D step-6 row empty, no `06` evidence anywhere; live staging state not verified this session (not authorized). Cutover held at Gate 2 |
| 2026-09-29T14:25Z | Qoder (laptop resumption) | Laptop read-only resumption checks 1–2 | Repo: branch `main` at `e8fb3b2` (PR #42 merge), zero tracked modifications, untracked set intact (12 entries incl. this audit). Audit on this machine: 49,578 bytes, last written 2026-09-29; contains §N rows through the desktop-handoff inspection (incl. `05b` PASS and desktop rows) — no newer execution evidence exists anywhere in the file: §D step-6 row still empty, no `06`/Gate-2 evidence. Local SQL integrity: 12/12 `scripts/f2-cutover/sql/*.sql` SHA-256 recomputed and equal to the approved recorded set (`01` = `d7cc08ab1840…`, `04` = `c15459f990fe…`, `05` = `de8f1c2e7aae…`, `05b` = `481d0b71c107…`, `06` = `a060fcf41690…`, `lib` = `5dfd8705c720…`). **Docker engine NOT running on this machine** (npipe `dockerDesktopLinuxEngine` unreachable) → `f2c` availability and its `/sql` hash set UNVERIFIED; container re-check pending Docker Desktop start (recreate + re-copy only if absent; never refresh from unmerged source). No credential values inspected or printed |
| 2026-09-29T14:25Z | Qoder (laptop resumption) | Check 4 prep — `04-verify-locking.sql` variable requirements verified | File line 20 `\ir lib-guards.sql` → requires the FULL nine-variable `$F2` block (`cutover_shop_id`, `pinned_shop_id`, `cutover_generation`, `write_role`, `read_role`, `expected_database`, `expected_role`, `expected_shops`, `expected_shop_members`); no step-4-extra variables (V1–V7 use only block vars). File is idempotent, read-only, never mutates. Full command withheld until (a) Docker Desktop up, (b) `f2c` present and 12/12 `/sql` hashes re-verified, (c) Chris's PG* vars re-entered with masked password entry (name-only forwarding incl. `PGSSLMODE`, `psql -X -w`). Freshness requirements identified before Gate 2 may be presented again: fresh `04` V1–V7 green; S8 process-continuity re-proof (last /proc snapshot 2026-09-24T07:38:10Z — does not cover the break); deployment-unchanged + `/api/v1/ready` baseline match; and read-only `05`+`05b` rerun (last passed 2026-09-25; a multi-day gap with machine handoff means zero-variance must be re-proven at the current point). `04` green proves current locking state only — not unchanged reconciliation, not process continuity |
| 2026-09-29T14:45Z | Qoder (laptop resumption) | Check 2 COMPLETE — `f2c` restored and 12/12 verified | Docker Desktop started by Chris; `docker ps -a` showed `f2c` (postgres:16) still EXISTING in `Exited (255)` state (did not auto-start this time; not deleted, not recreated — `docker start f2c` on the existing container only). `/sql` holds exactly 12 files; `sha256sum` set matches the approved recorded packet 12/12 (`01` = `d7cc08ab1840…` … `lib` = `5dfd8705c720…`), zero mismatches, no extra files. Baked container env carries only postgres:16 image defaults by NAME (`PG_VERSION`, `PG_MAJOR`, `PGDATA`) — no connection variables, no credentials; values never printed. Unrelated containers untouched: `stashtab-f2cut-bee09da4` (Created), `stashtab-pg-accept`, `mimir-redis`, `mimir-postgres` (Exited). No database commands run. Outstanding before the `04` command: Chris re-enters the six PG* vars in his private session with masked password entry |
| 2026-09-30 | Chris (private session) → Qoder | Check 4 — `04-verify-locking.sql` command PROVIDED, not yet executed | Chris confirmed all six PG* connection variables set in his private PowerShell session (name-liveness only; no values shared). Qoder handed the complete read-only invocation: `docker exec -e PGHOST -e PGPORT -e PGDATABASE -e PGUSER -e PGPASSWORD -e PGSSLMODE f2c psql -X -w -v ON_ERROR_STOP=1` with the full nine-variable `$F2` block (shop `798d40f4-0832-46c4-991b-050e1310f6c4` twice for G1b, generation 1, `write_role=stashtab_migrator`, `read_role=stashtab_api`, `expected_database=stashtab_staging`, `expected_role=stashtab_migrator`, `expected_shops=2`, `expected_shop_members=2`) and `-f /sql/04-verify-locking.sql`, `EXIT=$LASTEXITCODE` capture. Expected tokens: G1–G9 green, V1 `one-row-globally`, V2 `pinned-shop-gen1-only`, V3 `locking-with-frozen_at-and-no-opened_at`, V4 `gate-reads-locking`, V5 row id=1/gen 1/locking/opened_at NULL, V6 `no-receive-evidence`, V7 `reserved-and-probe-keys-unused`, EXIT=0. Any unexpected token, error or non-zero exit: stop, no automatic retry. Read-only; `01`/`03`/`06` not run; Gate 2 locked |
| 2026-09-30 | Chris (private session) → Qoder | Check 4 first attempt — FAILED fail-closed at container level, NOT a database event | Chris ran the exact provided `04` command; output: `Error response from daemon: container cb5776a2… is not running`, `EXIT=1`. Diagnosis: `docker ps -a` showed `f2c` in `Exited (255)` again (Docker engine restarted ~29 min earlier; same sleep-death pattern as the prior engine restart). psql never started, no connection attempt, no guard evaluation, no write, no credential exposure. Recovery: `docker start f2c` on the existing container only (not recreated, not deleted); container `Up`; `/sql` re-verified — exactly 12 files, full SHA-256 list byte-equal to the approved packet (`01` = `d7cc08ab1840…` … `lib` = `5dfd8705c720…`), zero mismatches, no extras. Chris re-running the identical `04` command; result pending |
| 2026-09-30 | Chris (private session) → Qoder | Check 4 — `04-verify-locking.sql` RESULT: PASS (row still `locking`, gate closed) | Re-run of the identical command after vehicle restoration. Output token set is `04`-specific and complete: G1 shop `798d40f4-0832-46c4-991b-050e1310f6c4`, G1b `shop-id-double-entry-agrees`, G2 `1`, G3 `stashtab_staging`, G4 `stashtab_migrator,stashtab_api`, G5 `no-unapproved-role-can-assume-stashtab_migrator`, G6 `no-superuser`, G7 `2/2`, G8 `shop-present-with-one-membership`, G9 `stashtab_migrator`; V1 `one-row-globally`; V2 `pinned-shop-gen1-only`; V3 `locking-with-frozen_at-and-no-opened_at`; V4 `gate-reads-locking`; V5 row id=1, pinned shop, generation 1, `locking`, frozen_at = created_at = `2026-09-21 00:58:16.503535+00` (byte-identical to the 2026-09-21/24 baselines), opened_at NULL; V6 `no-receive-evidence`; V7 `reserved-and-probe-keys-unused`; footer `validation complete: row is locking, gate is closed, no receive evidence`; `EXIT=0`. All tokens verified by exact equality. Scope note: this proves CURRENT locking state only — not unchanged reconciliation (05/05b last passed 2026-09-25) and not process continuity (S8 last proven 2026-09-24T07:38:10Z). Remaining freshness requirements before Gate 2 may be re-presented: credential-free staging probes (deployment-unchanged + `/api/v1/ready` baseline match), S8 `/proc` continuity re-proof via the authorized temporary-SSH method, and read-only `05` + `05b` reruns in Chris's private session. `01`/`03`/`06` not run; Gate 2 locked |
| 2026-10-01 | Chris → Qoder | Freshness checks 1–3 AUTHORIZED (read-only; stop on failure/unexpected change; no retries/repairs/rebaselining; `01`/`03` excluded; `06`/receive/deployment/privilege changes NOT authorized; Gate 2 only after evidence passes) | Authorization recorded verbatim in scope: (1) read-only staging deployment + readiness checks with correct evidence strength (unchanged deployment proves no-redeploy only); (2) S8 process continuity via the previously approved temporary-SSH method, inspection limited to the staging runtime, remove only this attempt's temporary access/material and verify cleanup, preserve pre-existing SSH files/keys; (3) read-only `05` then `05b` in Chris's private session, complete variable verification before each command, name-only credential forwarding incl. `PGSSLMODE`, `psql -X -w`, verify `05` output before issuing `05b`. Original baselines and `notification_baseline_state=absent` preserved |
| 2026-10-01 | Qoder | Freshness check 1 — **FAIL: UNEXPECTED CHANGES ON STAGING → SEQUENCE STOPPED** | `railway status` (workspace `Chris Chan's Projects`, project `StashTab Staging` `f59112ac…`, env `staging`): service `api` status **● Failed** (was `● Online`); linked deployment ID **`d9f3dfe2-785e-4c7f-b175-933dbcb2b7c9`** — a NEW deployment, NOT the recorded live `44317623-c881-4e4a-9615-984290e7dbd8` (created 2026-09-04). `railway deployment list -s api -e staging` shows `44317623` now **REMOVED** (plus three older REMOVED entries). `GET https://api-staging-d965.up.railway.app/api/v1/ready` → **HTTP 404** (baseline H-4: 200 with `reasons:[]`, `inventory_cutover:false`, `schema.inventory_truth:true`) — API not serving. Interpretation at correct strength: the staging api service HAS been redeployed since the 2026-09-24 verification, the new deployment failed, and the endpoint is down; the "deployment-unchanged" freshness precondition is FALSE and S8 process continuity for the pre-break process is now moot (that process is gone with the removed deployment). Database side unaffected by this observation: `04` passed 2026-09-30 (locking row intact in Neon). Per authorization: STOPPED on unexpected change — no retries, no repairs, no rebaselining; checks 2 (S8 SSH) and 3 (`05`/`05b`) NOT started; no temporary SSH material created; nothing deployed or changed by Qoder. Gate 2 cannot be re-presented. Escalated to owner: determine who/what created deployment `d9f3dfe2` (likely a push-triggered deploy; repo autodeploy config and recent pushes to be inspected by owner decision), whether the failed deployment touched schema/roles, and how to restore the staging api to the verified state — all outside this authorization |
