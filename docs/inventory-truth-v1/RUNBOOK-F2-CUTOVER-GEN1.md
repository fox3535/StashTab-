# RUNBOOK — F2 generation-1 cutover, Smoke Shop B

**Status:** `PREPARED — PROVEN LOCALLY — NOT EXECUTED — EXECUTION NOT APPROVED`

This runbook is the operator form of
`CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §3 steps 1–8, ordered by D-045
decisions 3 and 4. It executes **only** under a separate named cutover unlock
that names the shop, the actor, the reserved key, and the scope. Nothing in this
file has been run against staging, Neon, Railway, or Clerk. The SQL it invokes
was proven end-to-end twice against two fresh disposable PostgreSQL 16
databases; see `CHECKPOINT-F2-CUTOVER-EXECUTION-PACKET.md` §4.

| Item | Value |
| --- | --- |
| Tenant | Smoke Shop B |
| `shop_id` | `798d40f4-0832-46c4-991b-050e1310f6c4` |
| Generation | `1` only. No second generation, no second row. |
| Reserved key | `F2-CUT-GEN1-0001` — reserved, **never used by this runbook** |
| Database | Neon `stashtab_staging` |
| Write role | `stashtab_migrator` (owner of every F2 object) |
| Runtime role | `stashtab_api`; also `stashtab_worker`, `stashtab_readonly` |
| Identity baseline | `shops = 2`, `shop_members = 2` |
| Command set | `scripts/f2-cutover/sql/` (12 files) |
| Local proof | `scripts/f2-cutover/harness_f2_cutover.py` |

## 0. Session model, and the one deliberate deviation

D-045 decision 1 authorises **one private, time-bounded direct
`stashtab_migrator` session**. Every SQL file in this runbook runs inside that
one session.

The operations plan §3 labels steps 2, 5, and 7 "pooled `stashtab_api`,
read-only". This runbook uses the migrator session for those steps instead, for
two evidence-backed reasons:

1. D-045 decision 1 is a recorded decision and outranks the plan text. It
   authorises exactly one session; opening a second pooled session for the
   read-only steps would widen the credential surface for no gate benefit.
2. `notifications_truth.migrator._grant_runtime_privileges` grants SELECT to the
   runtime role on only six of the twelve notification relations
   (`notification_occurrence`, `notification_audit`,
   `notification_source_observation`, `notification_occurrence_transition`,
   `notification_delivery_attempt`, `notification_recovery_park`) and issues
   REVOKEs for the other six. R5 requires a zero check across **all twelve**, so
   a partial read is not acceptable and only the owning role can produce the
   complete digest.

Read-only-ness is therefore enforced by the SQL, not by the role: steps 2, 2b,
4, 5, 5b, 7 and 7b contain no DML at all, and steps 5, 5b, 7, 7b additionally
run inside `BEGIN; SET TRANSACTION READ ONLY`, which PostgreSQL refuses to let
write. Step 1 (`01-preflight.sql`) is catalog and privilege lookups only.

The only files that write are `03-write-locking.sql` (one INSERT),
`06-write-complete.sql` (one UPDATE) and `08-break-glass-locking.sql` (one
UPDATE). Nothing in the command set issues DELETE, TRUNCATE, DDL, a grant, a
role change, or a seed.

## 1. P0 — preconditions (gate, not an execution step)

Do not start unless every line is evidenced. Any unverifiable line is S11: stop
before writing anything.

- [ ] Named cutover unlock recorded, naming shop, actor, reserved key, scope.
- [ ] This runbook approved verbatim; `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md`
      §3–§7 unchanged since approval.
- [ ] Two-person rule in force: owner present, operator executing.
- [ ] Target is `stashtab_staging`. Not production. Not a local database.
- [ ] Railway autodeploy **off**; no deployment started during the window.
- [ ] No worker and no cron process running against the database.
- [ ] Exactly one API process; no restart during the window.
- [ ] No open incident touching inventory, identity, or notifications.
- [ ] `inventory_truth_cutover` is empty (proven by P7 in step 2 below).
- [ ] Audit template copied and open:
      `AUDIT-TEMPLATE-F2-CUTOVER-GEN1.md`.

## 2. Credential handling (step 1 and step 8)

### 2.1 Open the session — never a URL

The credential is held privately by the owner. It is typed into the session
environment once, is never written to a file, and never appears in a command
line, a log, a Git object, a Railway variable, or application configuration.

libpq environment variables are used **instead of** a connection URL precisely so
that no URL can be echoed into a shell history entry, a process listing, a CI
log, or an error message.

PowerShell (the operator's shell):

```powershell
$env:PGHOST     = Read-Host "Neon host"          # private, not committed
$env:PGPORT     = "5432"
$env:PGDATABASE = "stashtab_staging"
$env:PGUSER     = "stashtab_migrator"
$env:PGPASSWORD = Read-Host "Migrator password" -AsSecureString | `
                  [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                    [Runtime.InteropServices.Marshal]::SecureStringToBStr($_))
$env:PGSSLMODE  = "require"
```

POSIX equivalent: `read -rs PGPASSWORD; export PGPASSWORD` plus the same four
`export`s. Do **not** use `psql "postgres://user:pass@host/db"` in any form.

If this workstation has no native `psql`, run the client from a throwaway
`postgres:16` container and pass the same five variables with `docker exec -e`.
Destroy the container in step 8. Never pass the host or password as a positional
argument or inside a URL.

Confirm the session before anything else:

```powershell
psql -X -c "SELECT current_user, session_user, current_database(), version();"
```

Expected: `stashtab_migrator` / `stashtab_migrator` / `stashtab_staging` /
PostgreSQL 16.x. Any other answer is S11 — close the session and stop.

### 2.2 The session must not reach the application

`stashtab_truth_migrator_role` must stay **absent** from the API environment.
If it is ever set, `prohibited_feature_reasons()` adds `truth_migrator_role` and
`GET /api/v1/ready` returns `503` — that is S10. Check ready before step 3 and
again at step 7.

### 2.3 Destroy the temporary credential (step 8)

The Neon `stashtab_migrator` **role is retained**. Only the temporary local
copy of its password is removed.

```powershell
Remove-Item Env:PGPASSWORD, Env:PGHOST, Env:PGUSER, Env:PGDATABASE, Env:PGPORT
Clear-History; [void][System.Reflection.Assembly]::LoadWithPartialName("PSReadLine")
Remove-Item (Get-PSReadLineOption).HistorySavePath -ErrorAction SilentlyContinue
docker rm -f <client-container>   # only if a client container was used
```

Then record in the audit template: credential destroyed, wall-clock time, method,
and that the Neon migrator role was **not** deleted. Do not paste any value into
the record. If exposure is suspected at any point, that is S9: stop, the owner
rotates, and the event is recorded without printing any value.

## 3. Command conventions

All twelve files live in `scripts/f2-cutover/sql/`. They are stored with LF line
endings (`.gitattributes`) because psql keeps a trailing `\r` and that breaks
`\ir` and `\echo`. Do not re-save them as CRLF.

Every invocation passes `-X -v ON_ERROR_STOP=1`. Each file additionally sets
`\set ON_ERROR_STOP on` itself through `lib-guards.sql`, so the command set fails
closed even if the flag is forgotten.

Assertion convention: each invariant is a `SELECT CASE WHEN <holds> THEN
<evidence> ELSE current_setting('stashtab_f2.<invariant_name>') END`. A failed
invariant raises `unrecognized configuration parameter
"stashtab_f2.<invariant_name>"`, which names the exact check that failed, cannot
be swallowed by an error handler, and gives psql a non-zero exit. Three plausible
alternatives (a nonexistent function, a bad cast, a `DO` block) were each tested
against `postgres:16` and each is unsound; the reasoning is recorded in the
`lib-guards.sql` header.

A missing `-v` variable is not defaulted: psql emits the literal `:'name'`,
which is a syntax error and a non-zero exit.

Common variables, identical for every file:

```powershell
$F2 = @(
  "-v", "cutover_shop_id=798d40f4-0832-46c4-991b-050e1310f6c4",
  "-v", "pinned_shop_id=798d40f4-0832-46c4-991b-050e1310f6c4",
  "-v", "cutover_generation=1",
  "-v", "write_role=stashtab_migrator",
  "-v", "read_role=stashtab_api",
  "-v", "expected_database=stashtab_staging",
  "-v", "expected_role=stashtab_migrator",
  "-v", "expected_shops=2",
  "-v", "expected_shop_members=2"
)
$SQL = "scripts/f2-cutover/sql"
```

`cutover_shop_id` and `pinned_shop_id` are the same literal supplied **twice**.
Guard G1b compares them, so a mistyped tenant in one place stops the run before
any statement touches data. This is a double-entry control, not redundancy.

Run one file as:

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 -f "$SQL/01-preflight.sql"
if ($LASTEXITCODE -ne 0) { "STOP - exit $LASTEXITCODE" }
```

**A non-zero exit is never retried inside the same unlock.** Record the exact
`stashtab_f2.*` name, map it to a stop condition in §7, and stop.

## 4. Steps 1–8

### Step 1 — open the write session

§2.1. Record the wall-clock time, the actor, and the role name (never the
credential). Then confirm the app is unaffected:

```powershell
curl.exe -s -o ready-before.json -w "%{http_code}`n" "$STAGING_BASE/api/v1/ready"
```

Expected `200` with `"reasons": []` and `"inventory_cutover": false`. Any other
result is S10.

### Step 2 — preflight and baseline

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 -f "$SQL/01-preflight.sql"
psql -X -v ON_ERROR_STOP=1 @F2 -f "$SQL/02-baseline.sql"
psql -X -v ON_ERROR_STOP=1 @F2 -f "$SQL/02b-baseline-notification.sql"
```

`01-preflight.sql` proves P1–P8: the 13 inventory/identity relations and the 12
notification relations exist; `purchase_record.client_idempotency_key` is
`varchar(36)` and nullable; the partial unique index
`uq_purchase_record_shop_client_key` exists with 2 key columns and a predicate;
`stashtab_api` is SELECT-only on `inventory_truth_cutover` while
`stashtab_migrator` holds SELECT/INSERT/UPDATE; **the cutover relation is
globally empty (P7)**; and the server is PostgreSQL 16 or newer.

P7 has no resume path. If it fires, do not edit the assertion and do not delete
the row. Run `04-verify-locking.sql` to establish the real state, record it, and
stop for an owner decision.

**Capture these four values from the output and paste them into the audit
template.** They are inputs to later steps, so a transcription error is caught
by a digest mismatch rather than by a silent pass:

| Variable to pass later | Column printed by | Used by |
| --- | --- | --- |
| `baseline_excl_cutover` | `02-baseline.sql` | `07-final-verification.sql` (F6) |
| `base_r5_inventory` | `02-baseline.sql` | `05-r1-r7.sql` (R5a), `07` (F6b) |
| `base_r5_notification` | `02b-baseline-notification.sql` | `05b`, `07b` |
| `freeze_window_start` | `02-baseline.sql` | audit record only |

`baseline_digest` (all thirteen relations, including `inventory_truth_cutover`)
is printed for the record. F6 deliberately compares against
`baseline_excl_cutover`, because steps 3 and 6 are allowed to move exactly that
one relation; comparing against the all-inclusive digest would make F6 fail by
construction and would train the operator to ignore a red check.

Also record the bounded Railway log window: one startup marker, one process, no
worker or cron line. A second process or a new deployment is S8.

### Step 3 — write the generation-1 `locking` row

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 -f "$SQL/03-write-locking.sql"
```

One INSERT, in one explicit transaction, asserting its own post-state before
COMMIT: W0 the relation is empty, W0b this session may INSERT, W2 exactly one
row for the pinned shop at generation 1 and zero rows for any other shop or
generation, W3 `status = 'locking'` with `frozen_at` set and `opened_at` NULL.
W4 prints the row as written — paste it into the audit template.

**Do not write `complete` at this step.** A rerun stops at W0 (or, if W0 were
bypassed, at `uq_cutover_shop_generation`); recovery is `04-verify-locking.sql`,
never an edited assertion and never a DELETE.

### Step 4 — confirm writes are still closed

First the idempotent database-side validation, which may be rerun freely:

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 -f "$SQL/04-verify-locking.sql"
```

V4 prints `gate-reads-locking`: that is the exact value
`cutover_status(db, shop_id)` reads, so `ensure_inventory_mutations_ready()`
raises `FeatureNotReadyError("inventory_truth")` and the endpoint returns `503`.
V6 proves no receive evidence exists for the pinned shop. V7 proves
`F2-CUT-GEN1-0001`, `F2-PROBE-DO-NOT-USE` and `F2-TEST-0001` were never written.

Then the HTTP checks in §5. **Smoke Shop B must return `503` while `locking`.**
Anything else is S2.

### Step 5 — run and record R1–R7 while locked

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 `
  -v base_r5_inventory=<from step 2> `
  -v recon_timeout_ms=15000 -v lock_timeout_ms=5000 `
  -v worker_role=stashtab_worker -v readonly_role=stashtab_readonly `
  -f "$SQL/05-r1-r7.sql"

psql -X -v ON_ERROR_STOP=1 @F2 `
  -v base_r5_notification=<from step 2b> `
  -v recon_timeout_ms=15000 `
  -f "$SQL/05b-r5-notification.sql"
```

Both must exit zero **and** print every zero token listed in §6. Step 5 is not
complete until both files have run: `05` covers R1–R4, R5a, R5c, R6 and R7;
`05b` carries R5b. A partial reconciliation is a failure under D-045 decision 6,
not a pass.

The whole gate runs inside one `BEGIN; SET TRANSACTION READ ONLY` transaction
with `SET LOCAL statement_timeout` and `SET LOCAL lock_timeout`, so a timeout
aborts the transaction and exits non-zero. **Timeout is not green** (S4).

Record each invariant's output and, for R2/R3, the `r2_rows_examined` count: both
are **trivially** zero at step 5 because decision 4 defers the receive, and the
audit must say "trivial zero over 0 rows", never "receive proof".

### Step 6 — transition the same row to `complete`

Only if §6 shows every token, for both files:

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 -v gate_attestation=r1-r7-zero-variance `
  -f "$SQL/06-write-complete.sql"
```

T0 requires the attestation string exactly; a wrong or missing value stops
before the transaction opens. T0b requires the row to be `locking` with
`frozen_at` set, `opened_at` NULL, and total rowcount 1. Then one UPDATE
matching `shop_id` + `generation` + `status = 'locking'`, asserting through its
own `RETURNING` clause that exactly one row moved. `frozen_at` and `created_at`
are deliberately **not** in the SET list. T2 requires
`opened_at >= frozen_at`; T3 requires zero rows for other shops, other
generations, and any non-`complete` status; T4 requires the envelope still empty
for the pinned shop. T5 prints the row — paste it into the audit template.

Step 6 is not idempotent by design. A second run finds the row in `complete` and
stops at T0b rather than rewriting `opened_at`, which would erase the true
exposure window.

### Step 7 — verify cutover state

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 `
  -v baseline_excl_cutover=<from step 2> -v base_r5_inventory=<from step 2> `
  -v verify_timeout_ms=15000 `
  -f "$SQL/07-final-verification.sql"

psql -X -v ON_ERROR_STOP=1 @F2 `
  -v base_r5_notification=<from step 2b> -v verify_timeout_ms=15000 `
  -f "$SQL/07b-verify-notification.sql"
```

F1 re-evaluates R4 at its `complete` point; F2 proves the gate now reads
`complete`; F3 proves **exactly one** tenant has an open gate and no other shop
reads `complete`; F4 re-runs R1; F5 re-runs R6; F6 and F6b compare the step-2
digests; F7 proves the cutover rowcount is 1; F8 proves no receive was
performed. F9 prints the row.

Then the HTTP checks in §5 again: ready `200` with `reasons: []`, the **other**
shop still `503`. If any other shop's gate opened, that is S2 — treat it as a
tenant-isolation failure and go to §7 break-glass.

**The global readiness flag does not become true.** `features.inventory_cutover`
is a hard-coded `False` in `services/api/app/readiness.py` and this packet does
not change application code. A green cutover never implies a green readiness
payload, and no operator should expect one.

### Step 8 — stop, do not receive

- **No `POST` to the receive endpoint for Smoke Shop B.** The first successful
  receive requires the **separate** named unlock of D-045 decision 4.
- Close the migrator session.
- Destroy the temporary credential per §2.3. The Neon `stashtab_migrator` role
  is **retained**.
- Record the freeze-window end.
- `F2-CUT-GEN1-0001` stays unused. Confirm with V7 / F8 evidence.
- Fill the final decision block of the audit template, then hand off to the
  `R` record item: update `ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`, close
  the operations plan, update the gate pointer — on a new branch with a PR. Never
  a direct commit or push to `main`.

## 5. HTTP checks (steps 4 and 7)

`$STAGING_BASE` is the staging API base URL. It is not a secret and contains no
credential. `$TOKEN` is a real Clerk session token for a Smoke Shop B member,
held in the environment and never pasted into the audit record.

Every probe below is expected to **fail closed**. A `2xx` from the receive
endpoint at step 4 or step 7 is a violation of this runbook and an immediate
stop.

`probe-body.json` — a body that satisfies `ControlledReceiveIn`
(`admin.py` L1203–L1211) so that no probe is rejected for a schema reason and
masks the gate:

```json
{
  "sku": "F2-PROBE-DO-NOT-USE",
  "name": "F2 cutover probe - must never be received",
  "quantity": 1,
  "unit_cost": 0.01,
  "set_name": "Probe Set",
  "sequence_number": "1"
}
```

`F2-PROBE-DO-NOT-USE` is one of the three markers V7 and F8 assert are absent,
so if a probe ever did write, the packet detects it by name.

**Handler ordering, read from `admin.py` L1232–L1257.** Knowing the order is
what makes a status code interpretable:

1. `get_shop_context` → `401` when no authenticated user is present
   (`app/auth/identity.py` L76), resolved from the verified Clerk identity plus
   shop membership. `X-Shop-Id` is an untrusted hint, never identity.
2. `_require_receive_role` → `403` unless the resolved membership role is
   `owner` or `staff`.
3. `_validated_client_key` → `422` unless `Idempotency-Key` is present, is 36
   characters, and parses as UUID **version 4**.
4. `receive_controlled` → `ensure_inventory_mutations_ready` → `503`
   `FEATURE_NOT_READY` / `inventory_truth` while `cutover_status != 'complete'`.

The readiness gate is step **4**, so a `422` at step 3 says nothing about the
gate. That is the whole reason the probe key must be a fresh UUIDv4.

| # | Probe | Command | Expected | Stop |
| --- | --- | --- | --- | --- |
| H-1 | Unauthenticated receive | `curl.exe -s -o h1.json -w "%{http_code}" -X POST "$STAGING_BASE/api/v1/admin/inventory/receive" -H "Content-Type: application/json" -H "X-Shop-Id: 798d40f4-0832-46c4-991b-050e1310f6c4" -H "Idempotency-Key: <fresh-uuidv4>" -d '@probe-body.json'` | `401` | not `401` → S2 |
| H-2 | Authenticated receive, Smoke Shop B, while `locking` | same plus `-H "Authorization: Bearer $TOKEN"` | `503` with `{"error":"FEATURE_NOT_READY","feature":"inventory_truth"}` | not `503` → S2 |
| H-3 | Authenticated receive, **different** shop | `-H "X-Shop-Id: <other-shop-id>"` with that shop's member token | `503` | not `503` → S2, tenant isolation |
| H-3b | Non-UUID idempotency key (control probe) | H-2 with `-H "Idempotency-Key: F2-CUT-GEN1-0001"` | `422` — proves the key-validation step precedes the gate | `2xx` → stop |
| H-4 | Ready | `curl.exe -s -w "%{http_code}" "$STAGING_BASE/api/v1/ready"` | `200`, `"reasons": []` | otherwise → S10 |
| H-5 | Authenticated receive, Smoke Shop B, after step 6 | repeat H-2 | `503` for the **other** shop; **do not send H-2 for Smoke Shop B at all** | any `2xx` → stop, §7 |

`Idempotency-Key` **must be a valid UUIDv4 of exactly 36 characters.**
`admin.py::_validated_client_key` rejects anything else with `422` **before**
the readiness gate is reached, so a probe carrying a non-UUID key proves nothing
about the gate. This is why `F2-CUT-GEN1-0001` cannot be used as a probe key and
must not be: it is reserved, it is not a UUIDv4, and sending it would produce a
`422` that an operator could misread. See
`reviews/REVIEW-F2-CUTOVER-EXECUTION-PACKET.md` finding **P1-1** — the reserved
key is unusable as written and needs an owner decision under the later receive
unlock.

Record for each probe: wall clock, endpoint, HTTP status, the `error` and
`feature` fields of the body, and the request id from the Railway log line. Never
record the token.

**Proof that no successful receive was performed** is three-sided and all three
sides are required:

1. Every probe returned `>= 300` (H-1 to H-5, recorded above).
2. `04-verify-locking.sql` V6 and `07-final-verification.sql` F8 both print
   zero: no `purchase_record`, `acquisition_lot`, `inventory_event` or
   `inventory_item` row exists for the pinned shop.
3. The reserved and probe markers `F2-CUT-GEN1-0001`, `F2-PROBE-DO-NOT-USE`,
   `F2-TEST-0001` appear in `purchase_record.client_idempotency_key` zero times
   (V7, and F8's third clause).

## 6. Gate tokens that must all appear at step 5

From `05-r1-r7.sql`: `R1-zero`, `overlay-deltas-are-zero`,
`one-stock-row-per-sku`, `R2-zero`, `R3-zero`, `R4-zero`, `R5a-unchanged`,
`R5c-envelope-empty`, `R6-zero`, `R7a-zero`, `R7b-zero`, `R7c-zero`, `R7d-zero`,
`R7e-zero`, and `gate_evaluation_point = evaluating-at-locking`.

From `05b-r5-notification.sql`: `R5b-unchanged`,
`R5b-zero-rows-for-pinned-shop`, `nb1_evaluation_point = evaluating-at-locking`.

A missing token is a failure even if psql exited zero. Do not proceed to step 6
on a partial set.

| # | Invariant | Zero condition as implemented |
| --- | --- | --- |
| R1 | Snapshot vs append-only truth | Per-SKU `SUM(inventory_event.quantity_delta)` equals `inventory_item.stock` for every SKU of the shop, and the two aggregates are equal. Overlay events carry `quantity_delta = 0` and are asserted separately (R1c). R1d asserts `uq_inventory_shop_sku` exists, which is what makes one stock row per SKU provable rather than assumed. |
| R2 | Receive envelope completeness | Every `purchase_record` of the shop has an `acquisition_lot` and at least one `inventory_event`, joined on the locked canonical key `'purchase_record:' \|\| shop_id \|\| ':' \|\| id`. Orphan count `0`. Trivial at step 5. |
| R3 | Idempotency uniqueness | No duplicate `(shop_id, client_idempotency_key)`, no duplicate lot key, no duplicate event key; the reserved and probe keys produced `0` rows. Trivial at step 5. |
| R4 | Cutover row discipline | Exactly `1` row, pinned shop, generation `1`, `0` rows elsewhere. `locking` + `frozen_at` at step 5; `complete` + `opened_at` at step 7. |
| R5 | Out-of-scope writes | R5a: the six out-of-envelope inventory relations still match the step-2 digest. R5b: all twelve notification relations still match the step-2b digest **and** hold zero rows for the pinned tenant. R5c: the envelope is empty for the pinned shop. |
| R6 | Identity invariance | `shops = 2`, `shop_members = 2`, exactly one membership for the pinned shop. |
| R7 | Privilege invariance | R7a envelope grants on the four tables; R7b USAGE on the four F2 sequences; R7c PUBLIC holds nothing; R7d worker/readonly hold nothing; R7e the cutover write path. |

R1's SQL was written against frozen inventory-truth 1.3.0 and independently
reviewed: `reviews/REVIEW-F2-CUTOVER-R1-SQL.md`.

## 7. Break-glass — least-destructive return to `locking`

Permitted **only** to stop active harm: runaway or repeated writes, unexpected
cross-tenant visibility, privilege escalation, or an unrecoverable error
mid-transaction. It is **never** a way past a failed reconciliation — if R1–R7
were non-zero, stop under S3 and leave the row exactly as it is.

Declare it in the audit record first: trigger, wall clock, and the human owner
authorising it. Then:

```powershell
psql -X -v ON_ERROR_STOP=1 @F2 `
  -v break_glass_attestation=owner-authorized-break-glass `
  -v break_glass_timeout_ms=30000 `
  -f "$SQL/08-break-glass-locking.sql"
```

What it does, and what it refuses to do:

- Exactly one UPDATE of one existing row. `status` is the **only** column
  changed. `id`, `shop_id`, `generation`, `created_at`, `frozen_at` and
  `opened_at` are all preserved. `opened_at` in particular is evidence of how
  long the gate was open and is never nulled.
- No DELETE and no TRUNCATE anywhere in the file. The row survives.
- BG1 captures a catalog-wide row-count digest before the UPDATE and BG4
  recomputes it after, proving no relation anywhere gained or lost a row. BG3
  compares `created_at`, `frozen_at` and `opened_at` against a `\gset` pre-image.
- BG2 asserts through `RETURNING` that exactly one row moved and that its `id`
  equals the pre-image `id`. BG5 asserts total rowcount 1, zero rows for other
  shops, zero for other generations. BG6 asserts the gate reads `locking` again.
- BG0c refuses to run if the row is not `complete`, so a second invocation
  stops instead of reporting a withdrawal that did not happen.

No schema change, no privilege change, no role change, no seed, no redeploy, no
restart. The gate fail-closes on the status value alone.

After withdrawal: re-prove H-2 (`503` for Smoke Shop B), re-snapshot read-only,
compare against the step-2 baseline, freeze further attempts, open an incident
record, and do **not** retry inside the same unlock. Grant rollback runs only if
grants changed, via the reviewed path, and never widens grants. Schema rollback
is not part of a staging cutover: the column and the partial unique index are
additive and stay.

## 8. Stop conditions S1–S11 and evidence-preserving recovery

Stop immediately — **no retry inside the same unlock** — on any of these. In
every case: leave the data as it is, preserve the psql output verbatim, record
the `stashtab_f2.*` name or HTTP status, and fill the stop block of the audit
template. Recovery never deletes evidence.

| # | Trigger | Detection in this packet | First action |
| --- | --- | --- | --- |
| S1 | The write affects more than the named shop, or creates more than one row | W2/W3, T1/T3, BG2/BG5, F7 | Stop; §7 if the row reached `complete` |
| S2 | A receive for a non-cutover shop returns anything other than `503`, or Smoke Shop B is not `503` while `locking` | H-1, H-2, H-3, H-5, V4, F2, F3 | Stop; treat as tenant-isolation failure; §7 |
| S3 | Any R1–R7 invariant is non-zero | the named `stashtab_f2.*` parameter in §6 | Stop; **do not fix forward**; leave the row `locking` |
| S4 | Reconciliation errors, times out, or cannot complete | non-zero exit, `statement timeout`, `lock timeout`, missing token | Stop — timeout is not green |
| S5 | Unexpected privilege: runtime role can UPDATE/DELETE/TRUNCATE envelope tables, or any role can assume the migrator | P5/P6, R7a–R7e, G5/G6 | Stop; §7 step 4 grant rollback only if grants changed |
| S6 | Any write to a table outside the F2 envelope | R5a, R5b, F6, F6b, BG4 | Stop |
| S7 | A duplicate idempotency key produces a second row | R3a, R3b | Stop; contract violation |
| S8 | The API process restarts or crashes, or a new deployment appears in the window | Railway log window, step 2 and step 7 | Stop; autodeploy must stay off |
| S9 | Suspected credential exposure | any observation | Stop; owner rotates; record the event **without printing any value** |
| S10 | `/api/v1/ready` stops returning `200` with `reasons: []`, including reason `truth_migrator_role` | H-4 at step 1, step 4, step 7 | Stop; a migrator credential reached the app environment |
| S11 | Any `P0` precondition cannot be evidenced | §1 checklist, P7, G1–G9 | Stop before writing anything |

Rollback order — least destructive first, each verified before the next:

1. Withdraw the cutover row (`status` → `locking`) via §7 so the gate
   fail-closes and receive returns `503` again.
2. Rows already written by a receive are append-only evidence and are **not**
   deleted. Record them; reverse quantity effects only through the sanctioned
   append-only adjustment path in a separately approved slice.
3. Grant rollback only if grants changed.
4. No schema rollback: the column and partial unique index are additive and stay.
5. No redeploy, no restart, no production action, no seed.

## 9. Not authorized by this runbook

Executing the cutover itself; any successful receive; a second generation or a
second row; DELETE, TRUNCATE, fix-forward, or any seed; any deploy, redeploy,
autodeploy enablement, feature-flag or environment change; any grant, privilege
or role change; deleting the Neon `stashtab_migrator` role; any production
contact; any edit to frozen contract, design, migration, test or amendment text,
or to `GATES.md`; any claim that the global readiness flag becomes true; any
direct commit or push to `main`.

## 10. Relationship to other records

- Authority: `CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §3–§7, and D-045 in
  `docs/agent-context/DECISIONS.md`.
- Audit: `AUDIT-TEMPLATE-F2-CUTOVER-GEN1.md` (append-only, one per attempt).
- R1 review: `reviews/REVIEW-F2-CUTOVER-R1-SQL.md`.
- Packet record, local proof, and the bounded review:
  `CHECKPOINT-F2-CUTOVER-EXECUTION-PACKET.md` and
  `reviews/REVIEW-F2-CUTOVER-EXECUTION-PACKET.md`.
- Command set: `scripts/f2-cutover/sql/`; local proof harness:
  `scripts/f2-cutover/harness_f2_cutover.py`.
