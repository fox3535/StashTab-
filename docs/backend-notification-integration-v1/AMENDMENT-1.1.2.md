# AMENDMENT-1.1.2 — Immutable observation, occurrence, and transport history

**Identifier:** `STASHTAB-CARD-RESOLUTION-001 / AMENDMENT-1.1.2`  
**Parent:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0 (unchanged)  
**Parent policy set:** approved AMENDMENT-1.1.0 plus frozen AMENDMENT-1.1.1  
**Status:** `APPROVED AND FROZEN`  
**Proposed:** `2026-08-24`  
**Approved:** `2026-08-24`  
**Human vote:** APPROVE  
**Freeze manifest:** `docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`  
This file does not store its own SHA-256.  
**Frontend:** out of scope  
**Implementation:** disabled until a new named implementation unlock. The 1.1.1
unlock does not authorize 1.1.2 schema apply.

This amendment does not modify frozen 1.1.0 or 1.1.1 files. The three owner
decisions in §1 are accepted and must not be reopened.

Canonical 1.1.2 tables: 8 frozen 1.1.1 tables plus
`notification_source_observation`, `notification_occurrence_transition`,
`notification_delivery_attempt`, `notification_recovery_park` — **12 total**.

## 1. Accepted owner decisions (closed)

1. Active duplicates increment a durable event counter. They do not create a
   new occurrence or delivery generation.
2. Occurrence lifecycle is recorded in an append-only transition table.
   Occurrence rows remain append-only and do not gain a mutable status column.
3. Every provider attempt is recorded in one append-only attempt-log table
   with immutable `started` and `outcome` phases.

## 2. Source-observation idempotency

### 2.1 Identity

A source observation is one durable producer sighting of one durable source
for one shop.

Owning table: `notification_source_observation`.

Required columns:

| Column | Type / rule |
| --- | --- |
| `id` | `VARCHAR(36) NOT NULL` |
| `shop_id` | `VARCHAR(36) NOT NULL` |
| `source_kind` | `VARCHAR(64) NOT NULL` |
| `source_key` | `VARCHAR(255) NOT NULL` |
| `observation_token` | `VARCHAR(255) NOT NULL` |
| `event_id` | `VARCHAR(36) NOT NULL` |
| `occurrence_seq` | `INTEGER NOT NULL` |
| `created_at` | timestamptz `NOT NULL DEFAULT now()` |

Constraints:

- `PRIMARY KEY (id)`
- `UNIQUE (shop_id, source_kind, source_key, observation_token)`
- `CHECK (length(observation_token) >= 1)`
- `FOREIGN KEY (shop_id) REFERENCES shop(id) ON DELETE RESTRICT`
- `FOREIGN KEY (shop_id, event_id) REFERENCES notification_event(shop_id, id) ON DELETE RESTRICT`
- `FOREIGN KEY (shop_id, event_id, occurrence_seq) REFERENCES notification_occurrence(shop_id, event_id, occurrence_seq) ON DELETE RESTRICT`
- append-only: runtime `UPDATE`, `DELETE`, and `TRUNCATE` rejected

`observation_token` is a producer-supplied durable token.

Foreign keys from this table to `notification_event` and
`notification_occurrence` are `DEFERRABLE INITIALLY DEFERRED` so one
transaction can reserve the observation identity before the parent rows
exist. The observation row is still append-only after commit.

Pattern-B recovery sweep **always** uses token `initial` and never mints a
new token. After the first successful `initial` observation, later sweeps
are no-ops. They do not increment `occurrence_count` and do not reopen.

A genuine later Pattern-B observation (counting or reopen) is created only
when the producer supplies a new token. The producer token is
`{source_key}:{producer_observation_id}` where `producer_observation_id`
is a durable UUID or monotonic revision from the business producer. The
notification worker must not invent those tokens.

### 2.2 Event columns added by 1.1.2

On `notification_event`:

- `occurrence_count INTEGER NOT NULL DEFAULT 1`
- `last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `CHECK (occurrence_count >= 1)`

`occurrence_seq` remains the genuine-reopen generation from 1.1.1. It is
not incremented by an active duplicate observation.

This amendment **supersedes** DIRECTIVE §4.7 for `occurrence_count`:
`occurrence_count` is the active-duplicate counter and resets to `1` on
reopen. Event status `failed` is active, so a new observation increments
the count and does not reopen. Reopen remains only from `acknowledged`,
`resolved`, or `cancelled`.

### 2.3 Exact apply rules

Given `(shop_id, source_kind, source_key, observation_token)`:

Lock order is always `notification_source` then `notification_event` then
`notification_occurrence` then `notification_delivery`. Ack, cancel, worker
finalize, and apply all use that order.

1. Open a savepoint. If a `notification_source` row exists, `SELECT ... FOR UPDATE`
   it. If not, continue without a source row.
2. If `notification_source_observation` already has
   `(shop_id, source_kind, source_key, observation_token)`, roll back to the
   savepoint and return the existing event. This is a no-op.
3. If no source/event exists:
   - insert `notification_event` (`occurrence_seq=1`, `occurrence_count=1`,
     `last_seen_at=now()`, status `pending`)
   - insert `notification_occurrence` seq `1`
   - insert initial transition `NULL → pending` with `transition_seq=1`
   - insert `notification_source` bound to that event and seq `1`
   - insert the observation row bound to that event and seq `1`
   - if `notification_source` unique **or** `notification_event (shop_id, dedupe_key)`
     unique conflicts, roll back this savepoint, reload the winner
     source/event with `FOR UPDATE`, and continue at step 4 or 6. Do not
     keep a second event.
   - if the observation unique conflicts, roll back this savepoint and
     return the existing event (no-op).
   - stop. Do not increment `occurrence_count` on this create path.
4. If the observation is new and the locked event status is `pending`,
   `delivered`, or `failed`:
   - insert the observation bound to the current event and current
     `occurrence_seq`
   - if that unique insert conflicts, roll back this savepoint (no-op)
   - otherwise
     `UPDATE notification_event SET occurrence_count = occurrence_count + 1, last_seen_at = now() WHERE shop_id = :shop AND id = :event AND status IN ('pending','delivered','failed')`
   - insert `notification_audit` action `occurrence_count_increment`
   - do **not** insert `notification_occurrence`
   - do **not** increment `occurrence_seq`
   - do **not** create or increment delivery generations
   - if that update matches zero rows, follow step 6 in the same
     transaction; a committed observation must cause create, increment, or
     reopen
5. If the locked event status is `recorded`, roll back this savepoint and
   return. Routine events do not increment, reopen, or gain deliveries.
6. If the observation is new and the locked event status is `acknowledged`,
   `resolved`, or `cancelled`, this is a 1.1.1 reopen in the same transaction:
   - increment `occurrence_seq`
   - set event status `pending`, `occurrence_count = 1`, `last_seen_at = now()`
   - insert the new occurrence and initial `pending` transition
   - update `notification_source.occurrence_seq` to the new seq
   - insert new deliveries with `delivery_generation = 1`
   - insert the observation bound to the new `occurrence_seq`
   - insert `notification_audit` action `reopen`
   - prior occurrences, deliveries, observations, transitions, and attempts
     are retained
   - if the observation unique insert conflicts, roll back this savepoint
     (no-op)

Concurrent insert of the same observation: the observation unique
constraint admits at most one row. The losing transaction rolls back to
its savepoint, so it cannot increment, reopen, or leave an unbound event.

## 3. Occurrence transition state machine

Owning table: `notification_occurrence_transition`.

| Column | Type / rule |
| --- | --- |
| `id` | `VARCHAR(36) NOT NULL` |
| `shop_id` | `VARCHAR(36) NOT NULL` |
| `event_id` | `VARCHAR(36) NOT NULL` |
| `occurrence_seq` | `INTEGER NOT NULL` |
| `transition_seq` | `INTEGER NOT NULL` |
| `from_status` | `VARCHAR(24)` NULL only for the initial row |
| `to_status` | `VARCHAR(24) NOT NULL` |
| `cause` | `VARCHAR(255) NOT NULL` |
| `created_at` | timestamptz `NOT NULL DEFAULT now()` |

Constraints:

- `PRIMARY KEY (id)`
- `UNIQUE (shop_id, event_id, occurrence_seq, transition_seq)`
- `CHECK (transition_seq >= 1)`
- `CHECK (to_status IN ('pending','delivered','failed','cancelled'))`
- `CHECK ((transition_seq = 1 AND from_status IS NULL AND to_status = 'pending') OR (transition_seq > 1 AND from_status = 'pending' AND to_status IN ('delivered','failed','cancelled')))`
- `FOREIGN KEY (shop_id, event_id, occurrence_seq) REFERENCES notification_occurrence(shop_id, event_id, occurrence_seq) ON DELETE RESTRICT`
- append-only: runtime `UPDATE`, `DELETE`, and `TRUNCATE` rejected
- unique partial index `uq_notification_occurrence_initial_transition` on
  `(shop_id, event_id, occurrence_seq)` WHERE `transition_seq = 1`
- unique partial index `uq_notification_occurrence_terminal_transition` on
  `(shop_id, event_id, occurrence_seq)` WHERE
  `to_status IN ('delivered','failed','cancelled')`

Allowed transitions:

| from_status | to_status | When |
| --- | --- | --- |
| `NULL` | `pending` | occurrence created; `transition_seq` must be `1` |
| `pending` | `delivered` | any current-occurrence device `sent` and none remain `pending`/`retry_scheduled` |
| `pending` | `failed` | all current-occurrence devices terminal and none `sent`, or zero enabled devices at dispatch |
| `pending` | `cancelled` | owner cancels the event while this occurrence is current and still pending |

Forbidden: any other pair; any transition from `delivered`, `failed`, or
`cancelled`; a second `transition_seq = 1`; a second terminal row.

Next `transition_seq` is `COALESCE(MAX(transition_seq),0)+1` after
`SELECT ... FOR UPDATE` of the parent occurrence row in the same transaction.

Current occurrence status is `to_status` of the row with the greatest
`transition_seq` for `(shop_id, event_id, occurrence_seq)`. Timestamp order is
not authoritative.

An occurrence insert and its `transition_seq=1` row are the same
transaction. A later transition may be inserted only if `transition_seq=1`
already exists and the new seq equals `MAX(transition_seq)+1`. A lone
terminal row is forbidden.

Concurrent terminal inserts: the terminal partial unique index allows one
committed terminal row. The second insert fails. The loser must not retry as
`transition_seq=3`. Before inserting a terminal transition, the writer
`SELECT ... FOR UPDATE` the occurrence and every current-occurrence delivery,
then applies 1.1.1 clause 17 to those locked rows.

Worker finalization and owner cancel must write the event status change and
the occurrence transition in the **same transaction**. If a terminal
occurrence transition already exists, a second is forbidden. If the event is
`acknowledged` or `resolved`, the worker **must still** insert the
clause-17 occurrence terminal (`delivered` or `failed`) so the occurrence
does not remain pending after the last device finishes. If the event is
`cancelled`, no later `delivered`/`failed` occurrence transition is allowed.

## 4. Delivery-attempt model

Chosen schema: **one** append-only table `notification_delivery_attempt`.
There is no second table and no in-row mutation of attempt history.

| Column | Type / rule |
| --- | --- |
| `id` | `VARCHAR(36) NOT NULL` |
| `shop_id` | `VARCHAR(36) NOT NULL` |
| `delivery_id` | `VARCHAR(36) NOT NULL` |
| `attempt_number` | `INTEGER NOT NULL` |
| `phase` | `VARCHAR(16) NOT NULL` |
| `outcome` | `VARCHAR(24)` NULL on `started`; NOT NULL on `outcome` |
| `provider_status_code` | `INTEGER` NULL |
| `error` | `VARCHAR(500)` NULL |
| `created_at` | timestamptz `NOT NULL DEFAULT now()` |

Constraints:

- `PRIMARY KEY (id)`
- `UNIQUE (shop_id, delivery_id, attempt_number, phase)`
- `CHECK (attempt_number >= 1)`
- `CHECK (phase IN ('started','outcome'))`
- `CHECK (phase <> 'started' OR (outcome IS NULL AND provider_status_code IS NULL AND error IS NULL))`
- `CHECK (phase <> 'outcome' OR outcome IN ('sent','retry_scheduled','failed_exhausted','expired','provider_unknown','cancelled'))`
- `FOREIGN KEY (shop_id, delivery_id) REFERENCES notification_delivery(shop_id, id) ON DELETE RESTRICT`
- `notification_delivery` also has `UNIQUE (shop_id, id)` so this FK is legal
- append-only: runtime `UPDATE`, `DELETE`, and `TRUNCATE` rejected
- no payload, endpoint, `p256dh`, `auth`, VAPID, or raw provider-body columns
- `error` is optional, max 200 chars, and must not contain endpoints, keys,
  VAPID material, or raw provider bodies. Allowed: class name plus generic
  reason (`timeout`, `gone`, `rejected`, `unknown`)

`notification_delivery` gains `claimed_until TIMESTAMPTZ NULL`.

Exact write protocol:

1. Lock parent event `FOR UPDATE`, then claim the scheduling row with
   `SELECT ... FOR UPDATE SKIP LOCKED` where `claimed_until IS NULL OR claimed_until < now()`.
   Cancel and finalize use the same event-then-delivery order.
   In that same transaction set `attempt_count = attempt_count + 1`,
   `claimed_until = now() + interval '120 seconds'`, and insert
   `{phase='started', outcome=NULL, attempt_number = delivery.attempt_count}`.
   Commit before provider I/O. Heartbeat `claimed_until` if I/O exceeds 60s.
2. After provider response or recovery classification, insert one matching
   `{phase='outcome', outcome=...}` only if the `started` row for that
   `attempt_number` exists. Never update the `started` row. An `outcome`
   without `started` is forbidden. Clear `claimed_until` in the same
   outcome transaction.
3. Recovery may classify `started` without `outcome` only when
   `claimed_until < now()` (abandoned lease). A live send inside its lease
   must not be treated as a crash. Then:
   - if the scheduling row is `cancelled`, insert `outcome='cancelled'` and
     do not retry
   - otherwise insert exactly one `outcome='provider_unknown'` **before**
     scheduling any retry
   - do **not** increment `attempt_count` again; that number was claimed with
     `started`. The next retry uses `attempt_count + 1`.
   - if inserting `outcome` unique-conflicts, treat the row as already
     recovered; do not mark `sent` without an `outcome='sent'` row
4. `retry_scheduled` outcome may exist only when the scheduling row remains
   non-terminal and `attempt_count < 8`.
5. `sent`, `failed_exhausted`, `expired`, and `cancelled` outcomes must match
   the terminal scheduling-row status written in the same transaction.
6. Owner cancel of a current-occurrence delivery that has `started` and no
   `outcome` inserts `outcome='cancelled'` in the same cancel transaction.

`notification_delivery` remains the current scheduling projection (`status`,
`attempt_count`, `next_retry_at`, `attempted_at`, bounded `error`). It is not
the complete transport audit. Successful retries must not erase attempt-log
rows.

## 5. Schema inventory

### 5.1 Frozen 1.1.1 tables (8) — unchanged names

1. `notification_event`
2. `notification_occurrence`
3. `notification_delivery`
4. `notification_source`
5. `push_subscription`
6. `notification_preference`
7. `shop_notification_policy`
8. `notification_audit`

`notification_source` keeps `UNIQUE (shop_id, source_kind, source_key)` and
binds a durable source to one event. It does **not** own observation
idempotency. `notification_source.occurrence_seq` is updated on reopen.

`notification_delivery` gains `UNIQUE (shop_id, id)` in addition to the
frozen 1.1.1 five-column delivery identity.

`notification_audit.action` allowed values are exactly:
`critical_disable`, `critical_enable`, `test_send`, `ack`, `resolve`,
`cancel`, `reopen`, `occurrence_count_increment`.

### 5.2 1.1.2 additions

Column additions on `notification_event`:

- `occurrence_count INTEGER NOT NULL DEFAULT 1`
- `last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`

New tables (4):

9. `notification_source_observation` — owns source-observation uniqueness
10. `notification_occurrence_transition`
11. `notification_delivery_attempt`
12. `notification_recovery_park` — durable poison backoff for unrecovered sources

Each new table has `shop_id VARCHAR(36) NOT NULL`, `FOREIGN KEY (shop_id) REFERENCES shop(id) ON DELETE RESTRICT`, and `UNIQUE (shop_id, id)`.

`notification_recovery_park` columns: `id`, `shop_id`, `source_kind`, `source_key`, `fail_count INTEGER NOT NULL DEFAULT 0`, `next_at TIMESTAMPTZ NOT NULL`, `UNIQUE (shop_id, source_kind, source_key)`. Runtime may UPDATE `fail_count` and `next_at` only.

Canonical append-only enforcement on tables 9–11:

```
CREATE FUNCTION notification_reject_append_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_<table>_no_update BEFORE UPDATE ON <table>
  FOR EACH ROW EXECUTE FUNCTION notification_reject_append_mutation();
CREATE TRIGGER trg_<table>_no_delete BEFORE DELETE ON <table>
  FOR EACH ROW EXECUTE FUNCTION notification_reject_append_mutation();
CREATE TRIGGER trg_<table>_no_truncate BEFORE TRUNCATE ON <table>
  FOR EACH STATEMENT EXECUTE FUNCTION notification_reject_append_mutation();
```

Canonical terminal-delivery guard:

```
CREATE FUNCTION notification_reject_terminal_reopen() RETURNS trigger AS $$
BEGIN
  IF OLD.status IN ('sent','failed_exhausted','expired','cancelled')
     AND NEW.status IN ('pending','retry_scheduled') THEN
    RAISE EXCEPTION 'terminal delivery cannot reopen';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_notification_delivery_no_reopen BEFORE UPDATE ON notification_delivery
  FOR EACH ROW EXECUTE FUNCTION notification_reject_terminal_reopen();
```

Runtime role is not table owner and has no `TRIGGER` privilege. Grants: `SELECT,INSERT` on tables 9–11; `SELECT,INSERT,UPDATE` on `notification_recovery_park`; `UPDATE` on `notification_delivery` limited by the reopen trigger; `REVOKE TRUNCATE, DELETE` on all notification tables from the runtime role. Migrator role owns DDL and reconstruction DML.

Required database-side defaults on 1.1.1 columns that 1.1.1 already specified
as defaults, plus 1.1.2 additions:

- `notification_event.occurrence_seq DEFAULT 1`
- `notification_event.occurrence_count DEFAULT 1`
- `notification_event.last_seen_at DEFAULT now()`
- `notification_delivery.delivery_generation DEFAULT 1`
- `notification_delivery.attempt_count DEFAULT 0`
- `shop_notification_policy.critical_enabled DEFAULT TRUE`

### 5.3 Before / after counts

- Frozen 1.1.1 canonical tables: **8**
- 1.1.2 new tables: **4**
- Canonical tables after 1.1.2: **12**

The earlier eight-to-ten and eight-to-eleven drafts are withdrawn. Poison-recovery park is required so a failed source can back off without hiding later sources.

## 6. Closed carry-forward requirements and negative tests

Each item is a requirement, not an option.

| ID | Requirement | Negative acceptance test |
| --- | --- | --- |
| R1 | Cancel requires a verified JWT. Load the event as `(verified shop_id, id)` and require a current `shop_members` row for `(event.shop_id, actor)` with role `owner`. Unauthenticated is 401. Cross-shop or missing event is 404. Staff in the same shop receive 403. Owner cancel sets event `cancelled`, inserts occurrence transition `pending → cancelled` when the current occurrence is pending, sets every current-occurrence delivery in `pending` or `retry_scheduled` to `cancelled`, inserts `outcome='cancelled'` for any matching `started` attempt that has no outcome, and writes `notification_audit` action `cancel` with actor, prior, and new state. After cancel, materialization and due dispatch **must not** create or send further deliveries until a reopen. A send already claimed (`claimed_until >= now()`) may still complete at-least-once. | Unauthenticated cancel is 401. Shop B owner cancel of shop A event is 404. Staff cancel is 403 and no row changes. Owner cancel after pending occurrence leaves no open current-occurrence delivery. The next worker tick does not create or send a new delivery for that event. |
| R2 | Named defaults in **§5.2** exist as database defaults. Application defaults alone are insufficient. Adding `last_seen_at` to existing rows uses `USING created_at`, not `now()`. | Insert omitting those columns succeeds with the specified defaults. PostgreSQL `column_default` for each named column is not null. Existing-row `last_seen_at` equals `created_at`, not apply time. |
| R3 | Migrator compares constraint, index, and trigger **definitions** against this amendment: referenced columns, nullability, types, extra columns, ON DELETE action, uniqueness columns, check expressions, partial-index predicates, database defaults, trigger timing/events, and trigger function body. Name-only matches of a wrong definition abort and roll back the entire transaction, including reconstruction DML. `shop(id) ON DELETE RESTRICT` on every notification table is required and is not a failing “non-composite shop FK.” Failing “non-composite” means a child row whose only shop isolation is a nullable shop_id or a parent FK that omits `shop_id`. | Same-name FK with `ON DELETE CASCADE`, unique index missing its terminal `WHERE`, wrong trigger event, and extra non-canonical column are each rejected; no partial apply remains. |
| R4 | A delivery in `sent`, `failed_exhausted`, `expired`, or `cancelled` cannot return to `pending` or `retry_scheduled`. Runtime SQL and runtime role grants cannot perform that update. | Direct SQL update of `sent → pending` fails. Runtime role with ordinary delivery-update rights cannot rewrite a terminal delivery. |
| R5 | Immediately before provider I/O, the worker requires a current `shop_members` row for `(subscription.shop_id, subscription.clerk_user_id)`. Membership in a different shop does not count. There is no disabled-membership flag; revoke is delete of that shop row. Missing membership skips send, does not increment a successful send, writes attempt `outcome='expired'` if `started` was already inserted, omits that device from the due query and from clause-17 pending counts, and does not leak to other shops. | Delete shop A membership while the user remains in shop B, then tick shop A: no provider call for the shop A device; shop B devices still eligible; no `started` without `outcome`; the revoked shop A device does not occupy shop A’s 50-row due batch. |
| R6 | Test-send requires verified JWT plus current `shop_members` for `(shop_id, actor)`. Unauthenticated is 401; non-member is 403. Each request that passes the rate limit uses `source_kind='test'`, `source_key='test:{user_id}:{request_uuid}'`, and `dedupe_key='test:{user_id}:{request_uuid}'`, creating a new event. That explicitly supersedes the 1.1.1 hourly test identity. The 5/hour/user/shop limit is enforced in the same transaction as the event insert (PostgreSQL advisory lock or equivalent). Test-send cannot ack, reopen, resolve, or cancel a non-test event. | Unauthenticated test-send is 401. Shop B member cannot create a shop A test event. Two authorized test sends with one subscription produce two events, two `started` attempt rows, and two provider-send invocations; a sixth send in the window is 429 with no extra event. Concurrent fifth and sixth requests yield one 200 and one 429. |
| R7 | `NOTIFICATIONS_BACKEND_ENABLED=false` unmounts the notification router and skips recover/process. Inventory ticks continue. Flag-off does **not** DROP, truncate, or reverse reconstruction of the 12 notification tables. Re-enable resumes recover/process from remaining rows. This proposal does not apply schema in production and does not enable Web Push. | Flag-off process: notification routes 404; worker tick does not call recover/process; inventory worker path still runs; table count remains 12. |
| R8 | Materialization uses a stable event cursor and bounded batches. An event with more devices than one batch stays eligible. Clause 17 **must not** terminalize an occurrence while eligible current-occurrence device count is greater than existing current-occurrence deliveries. Already-due deliveries of a materialized subset may send, but the occurrence stays `pending` until materialization is complete or every existing delivery is terminal **and** no eligible device remains unmaterialized. Cancelled events are excluded from materialization. | Create `batch_limit + 1` devices. After tick 1, at least one due delivery may send, but the occurrence is still `pending`. After enough ticks every eligible device has a delivery. A full batch of incomplete events does not hide a later event. A cancelled event gains no new delivery on the next tick. |
| R9 | Recovery selects unrecovered eligible sources whose park is due: `NOT EXISTS notification_source` AND (`notification_recovery_park.next_at IS NULL OR next_at <= now()`) `ORDER BY source_kind, source_key LIMIT 100`. On apply failure, upsert `notification_recovery_park` `fail_count = fail_count + 1`, `next_at = now() + min(3600, 30 * 2^(fail_count-1))`. Parked-not-due sources are skipped, so later healthy sources are visible. Due parks are retried so a crash after business commit cannot permanently lose the alert. | 100 currently failing sources plus one later healthy source: after tick 1 the healthy source has a `notification_source` row. The 100 parked sources still recover after `next_at`. |
| R10 | Due query is shop-scoped: `event.status NOT IN ('cancelled','resolved') AND delivery.status IN ('pending','retry_scheduled') AND (next_retry_at IS NULL OR next_retry_at <= now()) ORDER BY COALESCE(next_retry_at, created_at) ASC, created_at ASC, id ASC LIMIT 50`. This supersedes 1.1.1 `NULLS FIRST` for fairness: a new pending row must not starve an older timestamped retry. Invalid-timezone and revoked-membership devices are **not** selected. | Future `next_retry_at` is skipped. An older due retry is selected before a newer pending row. One shop cannot consume another shop’s batch. |
| R11 | Preference timezone must be a valid IANA name at write time. Invalid values are 400 and are not stored. Existing invalid values, if any, fail closed: that device is omitted from the due query and is not treated as a pending device for clause 17. `next_retry_at` is not moved to a repeating hourly deferral. | PUT timezone `Not/A_Zone` returns 400. A injected invalid timezone is skipped by the due query and does not occupy the 50-row batch. |
| R12 | VAPID ready iff public key, private key, and subject are present and subject is `mailto:` with a local-part and domain (`[^@]+@[^@]+`) or `https:` with a host. `mailto:@`, `mailto:ops@example.com` placeholders, and any other scheme report disabled and forbid send. | Subject `ops@example.com`, `mailto:@`, `mailto:ops@example.com`, or `ftp://x` reports disabled; no provider call. |
| R13 | Default Web Push hosts are the frozen suffix list. Extra configured suffixes are ignored until a later approved amendment. Send-time DNS uses `getaddrinfo` with a 2-second deadline, rejects blocked IPs, and the HTTP adapter connects to the validated address tuple rather than re-resolving the hostname. TLS SNI and certificate verification use the original hostname, not the raw IP. Redirects remain forbidden. | Stub DNS first returning a public IP then a private IP: connect uses the first validated tuple or the send fails closed; no private connect. A pin that disables TLS hostname verify fails closed. Redirect 302 fails closed. |
| R14 | Replaying the same `(shop_id, source_kind, source_key, observation_token)` is a no-op. | Second apply of the same token leaves `occurrence_count`, occurrence rows, deliveries, and audit unchanged. |
| R15 | Two distinct tokens on an active event increment `occurrence_count` twice and do not insert a second occurrence. | Two tokens on `pending`: `occurrence_count=3` after the original create, still one occurrence. |
| R16 | Concurrent first-create of the same source leaves one event. | Two parallel creates: one `notification_event`, one source, no orphan event. |
| R17 | Concurrent terminal transitions leave one terminal row; the loser does not insert `transition_seq=3`. | Two parallel clause-17 finalizers: one terminal transition; occurrence status matches locked deliveries. |
| R18 | `started` and `attempt_count` increment are the same transaction. Recovery of `started` without `outcome` does not reuse that `attempt_number` for a second `started`. | Crash after `started`: one `provider_unknown` outcome; next send uses `attempt_count+1`. |
| R19 | Recovery writes `provider_unknown` only after `claimed_until < now()`. An in-lease send is not a crash. | Overlapping recovery tick during a live lease cannot insert `provider_unknown`. After lease expiry without outcome, recovery inserts `provider_unknown` and the next send uses `attempt_count+1`. |
| R20 | New observation, transition, and attempt queries always include `shop_id` from verified context or the persisted shop row. | Cross-shop SELECT by id alone returns no row. |

## 7. Migration reconstruction

DDL and reconstruction DML run in **one** PostgreSQL transaction. Failure
rolls back new columns, tables, triggers, grants, and backfill. A rerun
is a no-op: never overwrite live `occurrence_count` or `last_seen_at`;
insert observation, transition, and park rows only `WHERE NOT EXISTS`.

- Existing events: `UPDATE ... SET occurrence_count = 1, last_seen_at = created_at`
  only where those 1.1.2 columns are null. After first apply, live counters
  are left untouched.
- Existing sources: `INSERT notification_source_observation ... observation_token='initial'`
  `WHERE NOT EXISTS` that identity. Missing `initial` observation on a
  later rerun is filled; existing live tokens are not replaced.
- Existing occurrences: `INSERT transition_seq=1 NULL → pending WHERE NOT EXISTS`.
  Terminal `transition_seq=2` is inserted only when **that occurrence’s**
  deliveries alone prove 1.1.1 clause 17. Event-wide status is not copied
  onto an occurrence. Zero deliveries, `acknowledged`, `resolved`,
  `recorded`, mixed device rows, and reopened events with a still-pending
  current occurrence are **ambiguous** and stay pending. A cancelled event
  with a still-pending occurrence gets `pending → cancelled` for that
  current occurrence only.
- Existing deliveries: do not insert attempt rows. Absence of attempt rows
  is not an in-flight `started`. Recovery must not insert `provider_unknown`
  unless a `started` row exists. Fabricated `started`/`outcome` pairs are
  forbidden.
- Empty database: create all 12 tables in the same apply. Do not DROP or
  rewrite conflicting same-name objects; abort.
- Application `create_all` still cannot create these tables.

## 8. Freeze record

Human vote APPROVE 2026-08-24. Independent architecture, data-integrity,
database-security, application-security, adversarial/concurrency,
operations/rollback, and workflow-liveness reviews plus one bounded
correction pass are complete. Manifest:
`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`.
`FREEZE-1.1.1.json` and hashed 1.1.1 files stay byte-identical.

Reconstruction in §7 is future migrator behavior after a new named unlock
and the production-apply gate. This freeze does not apply schema, enable
VAPID, or enable Web Push.

Do not implement code, edit frozen 1.1.0/1.1.1 files, commit, push, merge,
deploy, or enable Web Push from this freeze.
