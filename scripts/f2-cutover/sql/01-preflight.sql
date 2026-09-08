-- Step 1/2 preflight: identity, database, role, schema, and envelope checks.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 2.
-- Session: the private, time-bounded direct migrator session.
--          Pass -v expected_role=<write_role>.
-- Writes: none. This file is read-only, and P1 to P8 are all catalog or
--         privilege lookups, so it is safe to rerun as often as needed.
--
-- Preflight fails closed if a cutover row already exists anywhere. That is
-- deliberate: the runbook has no "resume from an unknown state" path. If this
-- file stops at P7, do not edit the assertion and do not delete the row. Run
-- 04-verify-locking.sql to establish the real state, record it in the audit
-- template, and stop for an owner decision.

\ir lib-guards.sql

\echo '--- P1 required inventory and identity relations exist ---'
SELECT CASE
         WHEN (SELECT count(*)
                 FROM (VALUES ('inventory_item'), ('purchase_record'), ('sale'),
                              ('acquisition_lot'), ('inventory_event'),
                              ('inventory_truth_cutover'),
                              ('inventory_channel_observation'),
                              ('refund_record'), ('return_record'),
                              ('inventory_exception'), ('inventory_adjustment'),
                              ('shops'), ('shop_members')) AS required(rel)
                WHERE to_regclass('public.' || required.rel) IS NOT NULL) = 13
         THEN 'all-13-present'
         ELSE current_setting('stashtab_f2.f2_preflight_p1_required_relation_missing')
       END AS p1_required_relations;

\echo '--- P2 all twelve canonical notification relations exist ---'
-- Set taken verbatim from NOTIFICATION_TABLE_NAMES in
-- services/api/app/notifications_truth/models.py. R5 asserts zero rows across
-- exactly this set, so a missing member would make R5 silently partial.
SELECT CASE
         WHEN (SELECT count(*)
                 FROM (VALUES ('notification_event'), ('notification_occurrence'),
                              ('notification_delivery'), ('notification_source'),
                              ('push_subscription'), ('notification_preference'),
                              ('shop_notification_policy'), ('notification_audit'),
                              ('notification_source_observation'),
                              ('notification_occurrence_transition'),
                              ('notification_delivery_attempt'),
                              ('notification_recovery_park')) AS required(rel)
                WHERE to_regclass('public.' || required.rel) IS NOT NULL) = 12
         THEN 'all-12-present'
         ELSE current_setting('stashtab_f2.f2_preflight_p2_notification_relation_missing')
       END AS p2_notification_relations;

\echo '--- P3 F2 client idempotency column shape (AMENDMENT-1.3.0 section 4) ---'
SELECT CASE
         WHEN (SELECT count(*)
                 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'purchase_record'
                  AND column_name = 'client_idempotency_key'
                  AND data_type = 'character varying'
                  AND character_maximum_length = 36
                  AND is_nullable = 'YES') = 1
         THEN 'varchar(36)-nullable'
         ELSE current_setting('stashtab_f2.f2_preflight_p3_client_idempotency_column_shape_wrong')
       END AS p3_client_key_column;

\echo '--- P4 F2 partial unique index shape ---'
-- Expected on staging, recorded in
-- CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md:
--   CREATE UNIQUE INDEX uq_purchase_record_shop_client_key
--     ON public.purchase_record USING btree (shop_id, client_idempotency_key)
--     WHERE (client_idempotency_key IS NOT NULL)
SELECT CASE
         WHEN (SELECT count(*)
                 FROM pg_index i
                 JOIN pg_class c ON c.oid = i.indexrelid
                 JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = 'uq_purchase_record_shop_client_key'
                  AND i.indisunique
                  AND i.indpred IS NOT NULL
                  AND i.indnatts = 2) = 1
         THEN 'unique-partial-two-column'
         ELSE current_setting('stashtab_f2.f2_preflight_p4_client_key_index_shape_wrong')
       END AS p4_client_key_index;

\echo '--- P5 pooled runtime role cannot write the cutover row ---'
-- This is the property that makes the cutover a governed operation rather than
-- something the deployed application can do to itself.
SELECT CASE
         WHEN has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'SELECT')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'INSERT')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'UPDATE')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'DELETE')
          AND NOT has_table_privilege(:'read_role', 'public.inventory_truth_cutover', 'TRUNCATE')
         THEN 'select-only'
         ELSE current_setting('stashtab_f2.f2_preflight_p5_runtime_role_can_write_cutover_row')
       END AS p5_runtime_cutover_privileges;

\echo '--- P6 only the write role can change the cutover row ---'
SELECT CASE
         WHEN has_table_privilege(:'write_role', 'public.inventory_truth_cutover', 'SELECT')
          AND has_table_privilege(:'write_role', 'public.inventory_truth_cutover', 'INSERT')
          AND has_table_privilege(:'write_role', 'public.inventory_truth_cutover', 'UPDATE')
         THEN 'select-insert-update'
         ELSE current_setting('stashtab_f2.f2_preflight_p6_write_role_lacks_cutover_privileges')
       END AS p6_write_role_cutover_privileges;

\echo '--- P7 no cutover row exists anywhere yet ---'
-- Stop under S1 if this fails. See the header note: there is no resume path.
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 0
         THEN 'zero-rows-globally'
         ELSE current_setting('stashtab_f2.f2_preflight_p7_cutover_row_already_exists')
       END AS p7_cutover_empty;

\echo '--- P8 engine identity and server version ---'
-- The disposable proof runs PostgreSQL 16; staging runs Neon PostgreSQL 16.
-- The assertion is a floor, not an exact match, so a future minor upgrade does
-- not block the packet, but a different engine or an older server does.
SELECT CASE
         WHEN current_setting('server_version_num')::int >= 160000
         THEN 'postgresql-' || current_setting('server_version')
         ELSE current_setting('stashtab_f2.f2_preflight_p8_server_version_below_sixteen')
       END AS p8_server_version;

\echo '--- preflight complete: identity, database, role, schema, envelope ---'
