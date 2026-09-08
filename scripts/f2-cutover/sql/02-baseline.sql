-- Step 2 baseline capture: row counts, digests, identity, and freeze window.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 2.
-- Session: the private, time-bounded direct migrator session.
--          Pass -v expected_role=<write_role>. read_role is asserted by name
--          against the catalog and is never the session role.
-- Writes: none. Every statement here is a SELECT.
--
-- Scope: the thirteen inventory, truth, and identity relations that the accepted
-- inventory migrators provably grant SELECT on to the pooled runtime role.
-- Notification relations are counted by 02b-baseline-notification.sql instead,
-- because their SELECT grant depends on the notification slice's own runtime
-- role configuration and must not be assumed here. Splitting the two keeps
-- every count in this file backed by a grant the reviewed migrator asserts.
--
-- The four digests emitted below are inputs to later steps:
--
--   baseline_digest           all thirteen relations, including the cutover
--                             relation. This one is EXPECTED to change, because
--                             steps 3 and 6 write the cutover row. Recorded as
--                             the honest pre-cutover state.
--   baseline_excl_cutover     the same list minus inventory_truth_cutover.
--                             Compared again by 07-final-verification.sql F6 and
--                             passed as -v baseline_excl_cutover.
--   r5_inventory_digest       the six out-of-envelope inventory relations.
--                             Passed to 05-r1-r7.sql as -v base_r5_inventory and
--                             to 07-final-verification.sql as the same name.
--
-- Copy them into the audit template exactly as printed. Do not retype them.

\ir lib-guards.sql

\echo '--- B0 freeze window start (wall clock, server side) ---'
SELECT now() AS freeze_window_start,
       current_setting('TimeZone') AS session_time_zone;

\echo '--- B1 explicit per-relation baseline ---'
-- total_rows is the whole relation; cutover_shop_rows is the pinned tenant
-- only. Both are recorded because R5 reasons about "new rows" globally while
-- R1 to R4 reason about the pinned shop.
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
    ('inventory_truth_cutover',
     (SELECT count(*) FROM inventory_truth_cutover),
     (SELECT count(*) FROM inventory_truth_cutover WHERE shop_id = :'cutover_shop_id')),
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
SELECT rel,
       total_rows,
       cutover_shop_rows,
       md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows, '|')
             OVER ()) AS baseline_digest,
       md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows, '|')
             FILTER (WHERE rel <> 'inventory_truth_cutover')
             OVER ()) AS baseline_excl_cutover
FROM baseline
ORDER BY rel;

\echo '--- B2 r5_inventory baseline digest (out-of-envelope inventory relations) ---'
-- R5 counts rows outside the four-table F2 envelope
-- (inventory_item, purchase_record, acquisition_lot, inventory_event).
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
SELECT md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows, '|'
                      ORDER BY rel)) AS r5_inventory_digest
FROM out_of_envelope;

\echo '--- B3 envelope baseline for the pinned shop ---'
-- Under D-045 decision 4 the receive is deferred, so all four must be zero for
-- the pinned shop at this point. A non-zero value here is not a cutover
-- failure; it means the shop is not in the pre-receive state the runbook
-- assumes, and R2 and R3 would no longer be trivial zeros. Record it and stop
-- for an owner decision rather than continuing.
SELECT (SELECT count(*) FROM inventory_item    WHERE shop_id = :'cutover_shop_id') AS inventory_item_rows,
       (SELECT count(*) FROM purchase_record   WHERE shop_id = :'cutover_shop_id') AS purchase_record_rows,
       (SELECT count(*) FROM acquisition_lot   WHERE shop_id = :'cutover_shop_id') AS acquisition_lot_rows,
       (SELECT count(*) FROM inventory_event   WHERE shop_id = :'cutover_shop_id') AS inventory_event_rows,
       (SELECT count(*) FROM inventory_truth_cutover WHERE shop_id = :'cutover_shop_id') AS cutover_rows;

\echo '--- B4 identity and privilege baseline ---'
SELECT (SELECT count(*) FROM shops) AS shops,
       (SELECT count(*) FROM shop_members) AS shop_members,
       has_table_privilege(:'read_role', 'public.inventory_item', 'SELECT') AS api_item_select,
       has_table_privilege(:'read_role', 'public.inventory_item', 'INSERT') AS api_item_insert,
       has_table_privilege(:'read_role', 'public.inventory_item', 'UPDATE') AS api_item_update_wide,
       has_column_privilege(:'read_role', 'public.inventory_item', 'stock', 'UPDATE') AS api_item_update_stock,
       has_column_privilege(:'read_role', 'public.inventory_item', 'cost', 'UPDATE') AS api_item_update_cost,
       has_table_privilege(:'read_role', 'public.inventory_item', 'DELETE') AS api_item_delete,
       has_table_privilege(:'read_role', 'public.inventory_item', 'TRUNCATE') AS api_item_truncate;

\echo '--- baseline capture complete: run 02b-baseline-notification.sql next ---'
