-- Step 5: the zero-variance reconciliation gate R1 to R7, evaluated while the
-- generation-1 cutover row is 'locking'.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 5.
-- Invariants: same document, section 5, approved verbatim by D-045 decision 6.
-- Session: the private, time-bounded direct migrator session.
--          Pass -v expected_role=<write_role>. read_role is asserted by name
--          against the catalog and is never the session role.
-- Writes: none, and enforced. The whole gate runs inside one explicit
--         READ ONLY transaction, so any accidental write is rejected by
--         PostgreSQL rather than relying on the role's grants alone.
--
-- Additional required variables:
--
--   base_r5_inventory      r5_inventory_digest printed by 02-baseline.sql
--   recon_timeout_ms       statement timeout for the gate, e.g. 15000
--   lock_timeout_ms        lock timeout for the gate, e.g. 5000
--   worker_role            second runtime role, e.g. stashtab_worker
--   readonly_role          third runtime role, e.g. stashtab_readonly
--
-- R5 is delivered in two files. This one covers R5a (the six out-of-envelope
-- inventory relations) and R5c (the envelope is still empty for the pinned
-- shop). R5b (the twelve notification relations) lives in
-- 05b-r5-notification.sql because its SELECT grant depends on how the
-- notification slice was provisioned. Both files are part of step 5, and the
-- gate is not complete until both have printed zero. Running only this file and
-- reporting "R1 to R7 zero" would be a partial reconciliation, which D-045
-- decision 6 classifies as a failure.
--
-- D-045 decision 6: a timeout, partial response, exception, or mismatch is a
-- FAILURE. Success requires zero variance. Nothing in this file can report
-- success for an unfinished query, because the timeouts below turn a hang into
-- an error, and ON_ERROR_STOP turns an error into a non-zero exit.

\ir lib-guards.sql

\echo '--- additional parameter guards for step 5 ---'
SELECT CASE
         WHEN :'base_r5_inventory' ~ '^[0-9a-f]{32}$'
         THEN 'baseline-digest-present'
         ELSE current_setting('stashtab_f2.f2_gate_missing_or_invalid_baseline_digests')
       END AS g10_baseline_digests;

SELECT CASE
         WHEN :recon_timeout_ms BETWEEN 1000 AND 600000
          AND :lock_timeout_ms BETWEEN 100 AND 600000
         THEN :recon_timeout_ms || '/' || :lock_timeout_ms
         ELSE current_setting('stashtab_f2.f2_gate_timeout_parameters_out_of_range')
       END AS g11_timeout_parameters;

SELECT CASE
         WHEN :'worker_role' ~ '^[a-z][a-z0-9_]*$'
          AND :'readonly_role' ~ '^[a-z][a-z0-9_]*$'
         THEN :'worker_role' || ',' || :'readonly_role'
         ELSE current_setting('stashtab_f2.f2_gate_invalid_additional_role_names')
       END AS g12_additional_role_names;

BEGIN;

-- READ ONLY is set before any query in the transaction. It makes the claim
-- "step 5 writes nothing" a database-enforced property, not a convention.
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = :recon_timeout_ms;
SET LOCAL lock_timeout = :lock_timeout_ms;

\echo '--- gate precondition: the row is still locking ---'
-- If the row moved to complete before the gate ran, the evaluation point is
-- wrong and every expectation below is invalid. Stop; do not continue.
SELECT CASE
         WHEN (SELECT status FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation) = 'locking'
         THEN 'evaluating-at-locking'
         ELSE current_setting('stashtab_f2.f2_gate_precondition_row_is_not_locking')
       END AS gate_evaluation_point;

\echo '=== R1 legacy snapshot versus append-only truth ========================='
-- Authority: docs/inventory-truth-v1/DESIGN.md, "Locked recon (SKU),
-- receive-first slice":
--
--   event_remaining(shop_id, sku) = SUM(quantity_delta)
--                                   FROM inventory_event
--                                   WHERE shop_id = :shop_id AND sku = :sku
--   unaccounted if event_remaining != inventory_item.stock
--
-- and services/api/app/inventory_truth/core.py reconcile_shop(), which is the
-- accepted implementation of that text. Parity notes:
--
--   * No event_type filter. Overlay events are constrained to
--     quantity_delta = 0 by ck_overlay_zero_delta, so they
--     contribute nothing and must not be excluded by hand (R1c proves the
--     constraint actually holds on this data).
--   * acquisition_lot.quantity_acquired is denormalized evidence and is never
--     added to the sum. R1a prints it in a column named not_in_r1 on purpose.
--   * reconcile_shop() reports a mismatch for an event sku that has no
--     inventory_item row, whatever its delta. The FULL OUTER JOIN below
--     reproduces that with snapshot.sku IS NULL, which a COALESCE-to-zero
--     comparison alone would miss.
--   * reconcile_shop() treats a missing event total as 0. COALESCE(..., 0)
--     reproduces that.
\echo '--- R1a per-SKU variance detail (empty result set means zero variance) ---'
WITH event_remaining AS (
  SELECT sku, COALESCE(SUM(quantity_delta), 0)::bigint AS event_remaining
  FROM inventory_event
  WHERE shop_id = :'cutover_shop_id'
  GROUP BY sku
),
snapshot AS (
  SELECT sku, COALESCE(stock, 0)::bigint AS snapshot_stock
  FROM inventory_item
  WHERE shop_id = :'cutover_shop_id'
),
lot_total AS (
  SELECT sku, COALESCE(SUM(quantity_acquired), 0)::bigint AS lot_quantity_acquired
  FROM acquisition_lot
  WHERE shop_id = :'cutover_shop_id'
  GROUP BY sku
)
SELECT COALESCE(snapshot.sku, event_remaining.sku) AS sku,
       event_remaining.event_remaining,
       snapshot.snapshot_stock,
       COALESCE(event_remaining.event_remaining, 0)
         - COALESCE(snapshot.snapshot_stock, 0) AS variance,
       lot_total.lot_quantity_acquired AS not_in_r1
FROM snapshot
FULL OUTER JOIN event_remaining ON event_remaining.sku = snapshot.sku
LEFT JOIN lot_total ON lot_total.sku = COALESCE(snapshot.sku, event_remaining.sku)
WHERE snapshot.sku IS NULL
   OR COALESCE(event_remaining.event_remaining, 0) <> snapshot.snapshot_stock
ORDER BY 1;

\echo '--- R1c overlay events contribute zero delta, as the contract requires ---'
-- R1c and R1d are PRECONDITIONS for the R1b verdict and are deliberately
-- evaluated before it. If either fails, R1b's zero would mean something weaker
-- than "snapshot equals truth", so the gate must stop on the precondition and
-- never print the verdict. Under ON_ERROR_STOP the first failure aborts the
-- transaction, which is exactly the ordering an operator needs.
--
-- DESIGN.md: "Overlay events MUST set quantity_delta = 0. They never enter
-- remaining or recon." Proved here against the data rather than assumed, so an
-- overlay row with a non-zero delta cannot hide inside R1's zero result.
--
-- R1c has three arms, because the frozen text and the accepted implementation
-- do not cover the same set. Frozen DESIGN.md (quoted in
-- reviews/FREEZE-CHECK.md) defines:
--
--   OVERLAY = reserve | release | move | channel_commit | quarantine
--             | reverse (only if the reversed event is OVERLAY)
--
-- while ck_overlay_zero_delta in
-- services/api/app/inventory_truth/models_truth.py L82-L86 enforces only:
--
--   event_type NOT IN ('reserve','release','move','channel_commit','quarantine')
--   OR quantity_delta = 0
--
-- so a 'reverse' of an overlay event is NOT constrained by the schema even
-- though the frozen contract requires its delta to be 0. R1 cannot tell the
-- difference: it sums every delta with no event_type filter, so an
-- unconstrained non-zero 'reverse' delta would flow straight into
-- event_remaining and could be masked by a compensating error elsewhere.
--
-- The assertion therefore has four arms:
--   (a) ck_overlay_zero_delta exists on this database as a CHECK constraint,
--       so arm (b) is backed by the schema and not only by this query;
--   (b) zero rows of the five implemented overlay types carry a non-zero delta;
--   (c) zero 'reverse' rows whose reversed event is an overlay type carry a
--       non-zero delta -- the frozen clause the constraint does not enforce;
--   (d) zero 'reverse' rows with a dangling reverses_event_id, because arm (c)
--       is unevaluable if the reversed event cannot be resolved.
--
-- All four arms are trivially zero at step 5 under D-045 decision 4, because
-- no event row exists for the pinned shop before the later receive unlock.
-- They become substantive then, which is the point of writing them now.
WITH overlay_constraint AS (
  SELECT pg_get_constraintdef(con.oid) AS def
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname = 'inventory_event'
     AND con.conname = 'ck_overlay_zero_delta'
     AND con.contype = 'c'
),
implemented_overlay_violations AS (
  SELECT count(*) AS cnt
    FROM inventory_event
   WHERE shop_id = :'cutover_shop_id'
     AND event_type IN ('reserve', 'release', 'move',
                        'channel_commit', 'quarantine')
     AND quantity_delta <> 0
),
reverse_of_overlay AS (
  SELECT rev.id, rev.quantity_delta, rev.reverses_event_id
    FROM inventory_event rev
    LEFT JOIN inventory_event target
           ON target.id = rev.reverses_event_id
          AND target.shop_id = rev.shop_id
   WHERE rev.shop_id = :'cutover_shop_id'
     AND rev.event_type = 'reverse'
     AND rev.reverses_event_id IS NOT NULL
     AND target.event_type IN ('reserve', 'release', 'move',
                              'channel_commit', 'quarantine')
),
dangling_reverse AS (
  SELECT count(*) AS cnt
    FROM inventory_event rev
   WHERE rev.shop_id = :'cutover_shop_id'
     AND rev.event_type = 'reverse'
     AND rev.reverses_event_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM inventory_event target
                      WHERE target.id = rev.reverses_event_id
                        AND target.shop_id = rev.shop_id)
)
SELECT CASE
         WHEN (SELECT count(*) FROM overlay_constraint) = 1
          AND (SELECT count(*) FROM implemented_overlay_violations
                WHERE cnt = 0) = 1
          AND (SELECT count(*) FROM reverse_of_overlay
                WHERE quantity_delta <> 0) = 0
          AND (SELECT cnt FROM dangling_reverse) = 0
         THEN 'overlay-deltas-are-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r1c_overlay_event_has_a_non_zero_delta')
       END AS r1c_overlay_hygiene;

\echo '--- R1c detail: the constrained predicate as it exists on this database ---'
SELECT pg_get_constraintdef(con.oid) AS ck_overlay_zero_delta_definition
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public'
   AND c.relname = 'inventory_event'
   AND con.conname = 'ck_overlay_zero_delta';

\echo '--- R1d one snapshot stock row per sku, which is what makes R1b sound ---'
-- Load-bearing, not decorative. R1b joins the snapshot to the per-sku event sum
-- and compares them one to one. That comparison is equivalent to the accepted
-- implementation core.reconcile_shop() ONLY if inventory_item holds at most one
-- row per (shop_id, sku). reconcile_shop() pops each sku from its event map as
-- it walks the item rows, so a second row with the same sku would be compared
-- against 0; R1b would instead compare it against the full event sum. The two
-- readings can disagree, and R1b is the looser of the two.
--
-- The accepted schema forecloses the ambiguity: uq_inventory_shop_sku is
-- declared on the model (services/api/app/models/inventory.py) and created by
-- the reviewed migrator (services/api/app/inventory_live_schema/migrator.py,
-- _CREATE_INVENTORY_ITEM). R1d proves both halves rather than trusting the
-- model: the constraint exists, is UNIQUE, and covers exactly (shop_id, sku);
-- and the pinned tenant's data agrees with it. If the constraint is absent on
-- the target database, R1b's equivalence claim is unproven and the gate fails
-- closed here instead of returning a zero that means something weaker.
WITH constraint_shape AS (
  SELECT con.contype,
         (SELECT string_agg(a.attname, ',' ORDER BY k.ord)
            FROM unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a
              ON a.attrelid = con.conrelid
             AND a.attnum = k.attnum) AS cols
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname = 'inventory_item'
     AND con.conname = 'uq_inventory_shop_sku'
)
SELECT CASE
         WHEN (SELECT count(*) FROM constraint_shape
                WHERE contype = 'u' AND cols = 'shop_id,sku') = 1
          AND (SELECT count(*) FROM inventory_item
                WHERE shop_id = :'cutover_shop_id')
              = (SELECT count(DISTINCT sku) FROM inventory_item
                  WHERE shop_id = :'cutover_shop_id')
         THEN 'one-stock-row-per-sku'
         ELSE current_setting('stashtab_f2.f2_gate_r1d_snapshot_sku_key_discipline_not_provable')
       END AS r1d_snapshot_key_discipline;

\echo '--- R1b verdict: per-SKU mismatch count and aggregate variance both zero ---'
-- Evaluated last, after the R1c and R1d preconditions have held. Two-sided on
-- purpose: the per-SKU comparison reproduces core.reconcile_shop()'s mismatch
-- dict, and the aggregate comparison catches a pair of per-SKU errors that
-- cancel, which a sum-only check would miss and a per-SKU-only check would
-- still report. Both must be zero.
WITH event_remaining AS (
  SELECT sku, COALESCE(SUM(quantity_delta), 0)::bigint AS event_remaining
  FROM inventory_event
  WHERE shop_id = :'cutover_shop_id'
  GROUP BY sku
),
snapshot AS (
  SELECT sku, COALESCE(stock, 0)::bigint AS snapshot_stock
  FROM inventory_item
  WHERE shop_id = :'cutover_shop_id'
),
joined AS (
  SELECT COALESCE(snapshot.sku, event_remaining.sku) AS sku,
         COALESCE(event_remaining.event_remaining, 0) AS event_total,
         snapshot.snapshot_stock
  FROM snapshot
  FULL OUTER JOIN event_remaining ON event_remaining.sku = snapshot.sku
)
SELECT CASE
         WHEN (SELECT count(*) FROM joined
                WHERE snapshot_stock IS NULL
                   OR event_total <> snapshot_stock) = 0
          AND (SELECT COALESCE(SUM(event_total), 0) FROM joined)
              = (SELECT COALESCE(SUM(snapshot_stock), 0) FROM joined)
         THEN 'R1-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r1_snapshot_and_truth_variance')
       END AS r1_result;

\echo '--- R1e honest context: how many rows R1 actually compared ---'
-- R1 is zero-variance, but a zero over an empty set is not the same evidence as
-- a zero over a populated one. D-042 recorded the staging business tables as
-- empty, and D-045 decision 4 defers the receive, and this packet performs no
-- MIGRATION.md section 4 backfill: steps 1 to 8 write only the cutover row. So
-- at step 5 R1 is expected to compare zero snapshot rows against zero truth
-- rows, and its zero is trivial in exactly the sense the plan records for R2
-- and R3. These counts are printed so the audit entry must say "trivial zero
-- over N rows" rather than presenting R1 as a reconciliation of live stock.
-- If either count is non-zero at step 5, that is unexpected: something other
-- than this packet wrote to the envelope, and the attempt stops under S6.
SELECT (SELECT count(*) FROM inventory_item WHERE shop_id = :'cutover_shop_id')
         AS r1_snapshot_rows_examined,
       (SELECT count(*) FROM inventory_event WHERE shop_id = :'cutover_shop_id')
         AS r1_event_rows_examined,
       (SELECT count(DISTINCT sku) FROM inventory_item
         WHERE shop_id = :'cutover_shop_id') AS r1_snapshot_distinct_skus,
       (SELECT count(DISTINCT sku) FROM inventory_event
         WHERE shop_id = :'cutover_shop_id') AS r1_event_distinct_skus,
       (SELECT COALESCE(SUM(stock), 0) FROM inventory_item
         WHERE shop_id = :'cutover_shop_id') AS r1_snapshot_stock_sum,
       (SELECT COALESCE(SUM(quantity_delta), 0) FROM inventory_event
         WHERE shop_id = :'cutover_shop_id') AS r1_event_delta_sum;

\echo '=== R2 receive envelope completeness ===================================='
-- Approved wording: every purchase_record row for the shop has a matching
-- acquisition_lot and at least one inventory_event; orphan count 0.
-- The matching key is canonical_key() from core.py, whose locked format is
-- "purchase_record:{shop_id}:{source_pk}" with no ":receive" suffix.
-- Forward direction only, deliberately: backfilled opening and shrinkage lots
-- are keyed "{source}:{shop_id}:{pk}:gen:{n}" and are not derived from a
-- purchase_record, so a reverse orphan check would raise false positives and
-- is not part of the approved invariant.
\echo '--- R2a orphan detail (empty result set means zero orphans) ---'
SELECT pr.id AS purchase_record_id,
       pr.sku,
       (SELECT count(*) FROM acquisition_lot lot
         WHERE lot.shop_id = pr.shop_id
           AND lot.idempotency_key =
               'purchase_record:' || pr.shop_id || ':' || pr.id) AS matching_lots,
       (SELECT count(*) FROM inventory_event ev
         WHERE ev.shop_id = pr.shop_id
           AND ev.idempotency_key =
               'purchase_record:' || pr.shop_id || ':' || pr.id) AS matching_events
FROM purchase_record pr
WHERE pr.shop_id = :'cutover_shop_id'
ORDER BY pr.id;

\echo '--- R2b assertion: orphan count zero ---'
SELECT CASE
         WHEN (SELECT count(*) FROM purchase_record pr
                WHERE pr.shop_id = :'cutover_shop_id'
                  AND (
                    (SELECT count(*) FROM acquisition_lot lot
                      WHERE lot.shop_id = pr.shop_id
                        AND lot.idempotency_key =
                            'purchase_record:' || pr.shop_id || ':' || pr.id) = 0
                    OR
                    (SELECT count(*) FROM inventory_event ev
                      WHERE ev.shop_id = pr.shop_id
                        AND ev.idempotency_key =
                            'purchase_record:' || pr.shop_id || ':' || pr.id) = 0
                  )) = 0
         THEN 'R2-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r2_receive_envelope_orphans')
       END AS r2_result;

\echo '--- R2c honest context: how many receive rows R2 actually examined ---'
-- D-045 decision 4 defers the receive, so at this evaluation point R2 examines
-- zero rows and its zero is trivial. This count is recorded so the audit entry
-- can say "trivial zero over N rows" instead of presenting R2 as a receive
-- proof it did not perform.
SELECT (SELECT count(*) FROM purchase_record WHERE shop_id = :'cutover_shop_id')
         AS r2_rows_examined,
       (SELECT count(*) FROM acquisition_lot WHERE shop_id = :'cutover_shop_id')
         AS lot_rows_for_shop,
       (SELECT count(*) FROM inventory_event WHERE shop_id = :'cutover_shop_id')
         AS event_rows_for_shop;

\echo '=== R3 idempotency uniqueness ============================================='
\echo '--- R3a assertion: no duplicate client key, no duplicate truth key ---'
SELECT CASE
         WHEN (SELECT count(*) FROM (
                 SELECT client_idempotency_key
                 FROM purchase_record
                 WHERE shop_id = :'cutover_shop_id'
                   AND client_idempotency_key IS NOT NULL
                 GROUP BY client_idempotency_key
                 HAVING count(*) > 1) dup_client) = 0
          AND (SELECT count(*) FROM (
                 SELECT idempotency_key
                 FROM acquisition_lot
                 WHERE shop_id = :'cutover_shop_id'
                 GROUP BY idempotency_key
                 HAVING count(*) > 1) dup_lot) = 0
          AND (SELECT count(*) FROM (
                 SELECT idempotency_key
                 FROM inventory_event
                 WHERE shop_id = :'cutover_shop_id'
                 GROUP BY idempotency_key
                 HAVING count(*) > 1) dup_event) = 0
         THEN 'R3-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r3_duplicate_idempotency_key')
       END AS r3_result;

\echo '--- R3b the reserved and probe keys produced zero rows ---'
-- F2-CUT-GEN1-0001 is reserved by D-045 decision 5 for the later receive
-- unlock and must still be unused here. F2-PROBE-DO-NOT-USE and F2-TEST-0001
-- are earlier probe markers that may never be reused.
SELECT CASE
         WHEN (SELECT count(*) FROM purchase_record
                WHERE client_idempotency_key IN
                      ('F2-CUT-GEN1-0001', 'F2-PROBE-DO-NOT-USE', 'F2-TEST-0001')) = 0
         THEN 'replay-rows-added-0'
         ELSE current_setting('stashtab_f2.f2_gate_r3b_a_reserved_or_probe_key_was_written')
       END AS r3b_replay_rows_added;

\echo '=== R4 cutover row discipline at the locking evaluation point ============='
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'locking'
                  AND frozen_at IS NOT NULL) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id <> :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE generation <> :cutover_generation) = 0
          AND (SELECT count(*) FROM inventory_truth_cutover) = 1
         THEN 'R4-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r4_cutover_row_discipline')
       END AS r4_result;

\echo '=== R5 out-of-scope writes ================================================'
-- Approved wording: 0 new rows outside the F2 envelope and 0 rows in
-- notification tables. "New" means relative to the step-2 baseline, so R5
-- recomputes exactly the two digests 02-baseline.sql printed and compares them.
-- A digest mismatch is a stop under S6 even if the delta looks harmless: the
-- gate does not get to decide which out-of-scope write is acceptable.
\echo '--- R5a assertion: out-of-envelope inventory baseline unchanged ---'
WITH out_of_envelope(rel, total_rows, cutover_shop_rows) AS (
  VALUES
    ('inventory_adjustment',
     (SELECT count(*) FROM inventory_adjustment),
     (SELECT count(*) FROM inventory_adjustment WHERE shop_id = :'cutover_shop_id')),
    ('inventory_channel_observation',
     (SELECT count(*) FROM inventory_channel_observation),
     (SELECT count(*) FROM inventory_channel_observation WHERE shop_id = :'cutover_shop_id')),
    ('inventory_exception',
     (SELECT count(*) FROM inventory_exception),
     (SELECT count(*) FROM inventory_exception WHERE shop_id = :'cutover_shop_id')),
    ('refund_record',
     (SELECT count(*) FROM refund_record),
     (SELECT count(*) FROM refund_record WHERE shop_id = :'cutover_shop_id')),
    ('return_record',
     (SELECT count(*) FROM return_record),
     (SELECT count(*) FROM return_record WHERE shop_id = :'cutover_shop_id')),
    ('sale',
     (SELECT count(*) FROM sale),
     (SELECT count(*) FROM sale WHERE shop_id = :'cutover_shop_id'))
)
SELECT CASE
         WHEN md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows,
                             '|' ORDER BY rel)) = :'base_r5_inventory'
         THEN 'R5a-unchanged'
         ELSE current_setting('stashtab_f2.f2_gate_r5a_out_of_envelope_inventory_rows_changed')
       END AS r5a_result
FROM out_of_envelope;

\echo '--- R5b notification relations: see 05b-r5-notification.sql ---'
-- Deliberately not evaluated here. The twelve notification relations are not
-- part of the inventory envelope and their read grant is configured by the
-- notification slice, so counting them from this session could silently produce
-- a digest over a partial set. 05b-r5-notification.sql asserts the grant first
-- and fails closed if it is missing. Step 5 is incomplete without it.
SELECT 'R5b-deferred-to-05b-r5-notification.sql' AS r5b_pointer;

\echo '--- R5c the four envelope relations are still empty for the pinned shop ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_item   WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM purchase_record  WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM acquisition_lot  WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_event  WHERE shop_id = :'cutover_shop_id') = 0
         THEN 'R5c-envelope-empty'
         ELSE current_setting('stashtab_f2.f2_gate_r5c_envelope_rows_exist_for_the_pinned_shop')
       END AS r5c_result;

\echo '=== R6 identity invariance =================================================='
SELECT CASE
         WHEN (SELECT count(*) FROM shops) = :expected_shops
          AND (SELECT count(*) FROM shop_members) = :expected_shop_members
          AND (SELECT count(*) FROM shop_members
                WHERE shop_id = :'cutover_shop_id') = 1
         THEN 'R6-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r6_identity_changed')
       END AS r6_result;

\echo '=== R7 privilege invariance =================================================='
-- Envelope per AMENDMENT-1.3.0 section 7 as applied by
-- inventory_live_schema.migrator._grant_f2_envelope: SELECT and INSERT on the
-- four envelope tables, UPDATE restricted to (stock, cost) on inventory_item
-- only, USAGE on the four F2 sequences, nothing for PUBLIC, and no runtime
-- role able to assume the migrator.
\echo '--- R7a assertion: pooled runtime role envelope exactly as granted ---'
SELECT CASE
         WHEN (SELECT count(*)
                 FROM (VALUES ('inventory_item'), ('purchase_record'),
                              ('acquisition_lot'), ('inventory_event')) AS env(rel)
                WHERE has_table_privilege(:'read_role', 'public.' || env.rel, 'SELECT')
                  AND has_table_privilege(:'read_role', 'public.' || env.rel, 'INSERT')
                  AND NOT has_table_privilege(:'read_role', 'public.' || env.rel, 'DELETE')
                  AND NOT has_table_privilege(:'read_role', 'public.' || env.rel, 'TRUNCATE')
                  AND NOT has_table_privilege(:'read_role', 'public.' || env.rel, 'REFERENCES')
                  AND NOT has_table_privilege(:'read_role', 'public.' || env.rel, 'TRIGGER')) = 4
          AND has_column_privilege(:'read_role', 'public.inventory_item', 'stock', 'UPDATE')
          AND has_column_privilege(:'read_role', 'public.inventory_item', 'cost', 'UPDATE')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_item', 'UPDATE')
          AND NOT has_table_privilege(:'read_role', 'public.purchase_record', 'UPDATE')
          AND NOT has_table_privilege(:'read_role', 'public.acquisition_lot', 'UPDATE')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_event', 'UPDATE')
         THEN 'R7a-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r7a_runtime_envelope_privileges_changed')
       END AS r7a_result;

\echo '--- R7b assertion: sequence USAGE on exactly the four F2 sequences ---'
SELECT CASE
         WHEN (SELECT count(*)
                 FROM (VALUES ('inventory_item_id_seq'), ('purchase_record_id_seq'),
                              ('acquisition_lot_id_seq'), ('inventory_event_id_seq'))
                        AS seq(rel)
                WHERE has_sequence_privilege(:'read_role', 'public.' || seq.rel, 'USAGE')) = 4
         THEN 'R7b-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r7b_sequence_usage_changed')
       END AS r7b_result;

\echo '--- R7c assertion: PUBLIC holds nothing on the envelope ---'
SELECT CASE
         WHEN (SELECT count(*)
                 FROM pg_class c
                 JOIN pg_namespace n ON n.oid = c.relnamespace
                 CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl, '{}'::aclitem[])) a
                WHERE n.nspname = 'public'
                  AND c.relname IN ('inventory_item', 'purchase_record',
                                    'acquisition_lot', 'inventory_event')
                  AND a.grantee = 0) = 0
         THEN 'R7c-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r7c_public_holds_envelope_privileges')
       END AS r7c_result;

\echo '--- R7d assertion: worker and readonly hold no envelope privilege ---'
-- Conditional on existence: the reviewed migrators grant only to roles that
-- are present, so a deployment without one of them is not a variance.
SELECT CASE
         WHEN (SELECT count(*)
                 FROM (VALUES (:'worker_role'), (:'readonly_role')) AS extra(rel)
                 JOIN pg_roles r ON r.rolname = extra.rel
                 JOIN (VALUES ('inventory_item'), ('purchase_record'),
                            ('acquisition_lot'), ('inventory_event')) AS env(t)
                      ON true
                WHERE has_table_privilege(r.rolname, 'public.' || env.t, 'SELECT')
                   OR has_table_privilege(r.rolname, 'public.' || env.t, 'INSERT')
                   OR has_table_privilege(r.rolname, 'public.' || env.t, 'UPDATE')
                   OR has_table_privilege(r.rolname, 'public.' || env.t, 'DELETE')
                   OR has_table_privilege(r.rolname, 'public.' || env.t, 'TRUNCATE')) = 0
         THEN 'R7d-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r7d_secondary_runtime_role_holds_envelope_privileges')
       END AS r7d_result;

\echo '--- R7e assertion: the cutover row is still writable only by the write role ---'
SELECT CASE
         WHEN has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'SELECT')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'INSERT')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'UPDATE')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'DELETE')
          AND has_table_privilege(:'write_role', 'public.inventory_truth_cutover', 'INSERT')
          AND has_table_privilege(:'write_role', 'public.inventory_truth_cutover', 'UPDATE')
         THEN 'R7e-zero'
         ELSE current_setting('stashtab_f2.f2_gate_r7e_cutover_write_path_changed')
       END AS r7e_result;

\echo '=== gate summary =========================================================='
-- One row per invariant, so the audit template can be filled from a single
-- result set. Every value must read zero; anything else stops the attempt
-- under S3 and forbids the transition in 06-write-complete.sql.
SELECT 'R1' AS invariant, 'snapshot-versus-truth' AS subject, 'zero' AS required
UNION ALL SELECT 'R2', 'receive-envelope-orphans', 'zero'
UNION ALL SELECT 'R3', 'idempotency-duplicates', 'zero'
UNION ALL SELECT 'R4', 'cutover-row-discipline-locking', 'zero'
UNION ALL SELECT 'R5', 'out-of-scope-writes (R5a and R5c here, R5b in 05b)', 'unchanged'
UNION ALL SELECT 'R6', 'identity-invariance', 'zero'
UNION ALL SELECT 'R7', 'privilege-invariance', 'zero'
ORDER BY invariant;

COMMIT;

\echo '--- step 5 partial: R1 to R4, R5a, R5c, R6, R7 evaluated at the locking point ---'
\echo '--- next: 05b-r5-notification.sql, then 06-write-complete.sql only if every ---'
\echo '--- assertion in both files printed zero ---'
