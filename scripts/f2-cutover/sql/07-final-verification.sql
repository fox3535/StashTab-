-- Step 7: final verification of the cutover state.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 7.
-- Session: the private, time-bounded direct migrator session.
--          Pass -v expected_role=<write_role>. read_role is asserted by name
--          against the catalog and is never the session role.
-- Writes: none, and enforced by an explicit READ ONLY transaction.
--
-- Additional required variables:
--
--   baseline_excl_cutover  baseline_excl_cutover printed by 02-baseline.sql
--   base_r5_inventory      r5_inventory_digest printed by 02-baseline.sql
--   verify_timeout_ms      statement timeout for verification, e.g. 15000
--
-- Notification relations are verified by 07b-verify-notification.sql, for the
-- same grant reason given in 02b and 05b. Step 7 is not complete until both
-- files have printed their expected values.
--
-- This file re-evaluates R4 at its 'complete' evaluation point and re-runs R1
-- and R6, then compares the step-2 digests. It does not repeat the whole gate:
-- step 5 is the gate, and D-045 decision 3 fixes R4 as the one invariant
-- evaluated twice against the same single row.

\ir lib-guards.sql

SELECT CASE
         WHEN :'baseline_excl_cutover' ~ '^[0-9a-f]{32}$'
          AND :'base_r5_inventory' ~ '^[0-9a-f]{32}$'
         THEN 'baseline-digests-present'
         ELSE current_setting('stashtab_f2.f2_verify_missing_or_invalid_baseline_digests')
       END AS g13_baseline_digests;

SELECT CASE
         WHEN :verify_timeout_ms BETWEEN 1000 AND 600000
         THEN :verify_timeout_ms::text
         ELSE current_setting('stashtab_f2.f2_verify_timeout_parameter_out_of_range')
       END AS g14_timeout_parameter;

BEGIN;

SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = :verify_timeout_ms;

\echo '--- F0 freeze window end (wall clock, server side) ---'
SELECT now() AS freeze_window_end;

\echo '--- F1 R4 at its complete evaluation point ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'complete'
                  AND frozen_at IS NOT NULL
                  AND opened_at IS NOT NULL
                  AND opened_at >= frozen_at) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id <> :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE generation <> :cutover_generation) = 0
          AND (SELECT count(*) FROM inventory_truth_cutover) = 1
         THEN 'R4-zero-at-complete'
         ELSE current_setting('stashtab_f2.f2_verify_f1_r4_cutover_row_discipline_at_complete')
       END AS f1_r4_result;

\echo '--- F2 the value the application gate reads for the pinned shop ---'
-- cutover_status() reads the first row for the shop unordered. With exactly one
-- row, proven by F1, that read is deterministic and now returns 'complete', so
-- ensure_inventory_mutations_ready() stops raising for this shop and for no
-- other shop.
SELECT CASE
         WHEN (SELECT status FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                LIMIT 1) = 'complete'
         THEN 'gate-reads-complete'
         ELSE current_setting('stashtab_f2.f2_verify_f2_gate_does_not_read_complete')
       END AS f2_gate_visible_status;

\echo '--- F3 exactly one tenant has an open gate ---'
-- Every other shop must still resolve to NULL and therefore stay fail-closed.
-- Stop under S2 if more than one tenant reads complete.
SELECT CASE
         WHEN (SELECT count(*) FROM shops s
                WHERE (SELECT c.status FROM inventory_truth_cutover c
                        WHERE c.shop_id = s.id
                        LIMIT 1) = 'complete') = 1
          AND (SELECT count(*) FROM shops s
                WHERE s.id <> :'cutover_shop_id'
                  AND (SELECT c.status FROM inventory_truth_cutover c
                        WHERE c.shop_id = s.id
                        LIMIT 1) = 'complete') = 0
         THEN 'one-tenant-open'
         ELSE current_setting('stashtab_f2.f2_verify_f3_more_than_one_tenant_has_an_open_gate')
       END AS f3_open_gate_tenants;

\echo '--- F4 R1 re-evaluated at the complete point ---'
-- Same join as R1b, so it inherits the same precondition: one inventory_item
-- row per (shop_id, sku). That is proved by R1d at step 5 against
-- uq_inventory_shop_sku. Steps 6 and 7 perform no DDL and run inside READ ONLY
-- transactions, so the constraint proved at step 5 still holds here and R1d is
-- not repeated. If step 5 was skipped, F4's zero is not evidence and the
-- attempt must stop under S11 rather than continue.
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
         ELSE current_setting('stashtab_f2.f2_verify_f4_r1_variance_at_complete')
       END AS f4_r1_result;

\echo '--- F5 R6 identity invariance still holds ---'
SELECT CASE
         WHEN (SELECT count(*) FROM shops) = :expected_shops
          AND (SELECT count(*) FROM shop_members) = :expected_shop_members
          AND (SELECT count(*) FROM shop_members
                WHERE shop_id = :'cutover_shop_id') = 1
         THEN 'R6-zero'
         ELSE current_setting('stashtab_f2.f2_verify_f5_identity_changed_during_cutover')
       END AS f5_r6_result;

\echo '--- F6 the inventory and identity baseline is unchanged ---'
-- Steps 3 and 6 write only the cutover row, so this comparison uses the
-- baseline_excl_cutover digest from step 2, which covers exactly the twelve
-- relations listed below and deliberately excludes inventory_truth_cutover.
-- The cutover relation is asserted separately by F1 and F7. Including it here
-- would make F6 fail by construction and would train the operator to ignore a
-- red check.
WITH baseline(rel, total_rows, cutover_shop_rows) AS (
  VALUES
    ('acquisition_lot',
     (SELECT count(*) FROM acquisition_lot),
     (SELECT count(*) FROM acquisition_lot WHERE shop_id = :'cutover_shop_id')),
    ('inventory_adjustment',
     (SELECT count(*) FROM inventory_adjustment),
     (SELECT count(*) FROM inventory_adjustment WHERE shop_id = :'cutover_shop_id')),
    ('inventory_channel_observation',
     (SELECT count(*) FROM inventory_channel_observation),
     (SELECT count(*) FROM inventory_channel_observation WHERE shop_id = :'cutover_shop_id')),
    ('inventory_event',
     (SELECT count(*) FROM inventory_event),
     (SELECT count(*) FROM inventory_event WHERE shop_id = :'cutover_shop_id')),
    ('inventory_exception',
     (SELECT count(*) FROM inventory_exception),
     (SELECT count(*) FROM inventory_exception WHERE shop_id = :'cutover_shop_id')),
    ('inventory_item',
     (SELECT count(*) FROM inventory_item),
     (SELECT count(*) FROM inventory_item WHERE shop_id = :'cutover_shop_id')),
    ('purchase_record',
     (SELECT count(*) FROM purchase_record),
     (SELECT count(*) FROM purchase_record WHERE shop_id = :'cutover_shop_id')),
    ('refund_record',
     (SELECT count(*) FROM refund_record),
     (SELECT count(*) FROM refund_record WHERE shop_id = :'cutover_shop_id')),
    ('return_record',
     (SELECT count(*) FROM return_record),
     (SELECT count(*) FROM return_record WHERE shop_id = :'cutover_shop_id')),
    ('sale',
     (SELECT count(*) FROM sale),
     (SELECT count(*) FROM sale WHERE shop_id = :'cutover_shop_id')),
    ('shop_members',
     (SELECT count(*) FROM shop_members),
     (SELECT count(*) FROM shop_members WHERE shop_id = :'cutover_shop_id')),
    ('shops',
     (SELECT count(*) FROM shops),
     (SELECT count(*) FROM shops WHERE id = :'cutover_shop_id'))
)
SELECT CASE
         WHEN md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows,
                             '|' ORDER BY rel))
              = :'baseline_excl_cutover'
         THEN 'baseline-unchanged-excluding-cutover-row'
         ELSE current_setting('stashtab_f2.f2_verify_f6_baseline_changed_outside_the_cutover_row')
       END AS f6_baseline_stability
FROM baseline;

\echo '--- F6b the out-of-envelope inventory digest still matches step 2 ---'
-- Steps 3 and 6 are allowed to write the cutover row and nothing else. If an
-- out-of-envelope inventory relation moved between step 2 and step 7, something
-- other than this packet wrote to the database and the attempt stops under S6.
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
         THEN 'R5a-unchanged-at-step-7'
         ELSE current_setting('stashtab_f2.f2_verify_f6b_out_of_scope_rows_changed_during_the_cutover')
       END AS f6b_r5a_stability
FROM out_of_envelope;

\echo '--- F7 the cutover relation moved by exactly one row ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id') = 1
         THEN 'cutover-rowcount-1'
         ELSE current_setting('stashtab_f2.f2_verify_f7_cutover_rowcount_wrong')
       END AS f7_cutover_rowcount;

\echo '--- F8 no receive was performed by this packet ---'
-- Step 8 of the runbook stops without any POST. F8 is the database half of that
-- proof: the envelope is still empty for the pinned tenant and neither the
-- reserved key nor either probe marker was ever written.
SELECT CASE
         WHEN (SELECT count(*) FROM purchase_record WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM acquisition_lot WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_event WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_item   WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM purchase_record
                WHERE client_idempotency_key IN
                      ('F2-CUT-GEN1-0001', 'F2-PROBE-DO-NOT-USE', 'F2-TEST-0001')) = 0
         THEN 'no-receive-performed'
         ELSE current_setting('stashtab_f2.f2_verify_f8_a_receive_row_exists_and_step_8_was_violated')
       END AS f8_no_receive_performed;

\echo '--- F9 the row exactly as it stands (audit evidence) ---'
SELECT id, shop_id, generation, status, frozen_at, opened_at, created_at
FROM inventory_truth_cutover
ORDER BY shop_id, generation, id;

COMMIT;

\echo '--- step 7 partial: cutover verified, one tenant open, no receive performed ---'
\echo '--- next: 07b-verify-notification.sql, then step 8 STOP. Destroy the ---'
\echo '--- temporary credential. Do not POST to the receive endpoint. ---'
