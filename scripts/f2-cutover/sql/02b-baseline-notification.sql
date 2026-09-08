-- Step 2b baseline capture for the notification relations.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 2, and
--               section 5 invariant R5 ("0 rows in notification tables").
-- Session: the private, time-bounded direct migrator session, which owns the
--          notification relations and therefore holds SELECT on all twelve.
--          Pass -v expected_role=<write_role>.
-- Writes: none. Every statement here is a SELECT.
--
-- Why this is a separate file from 02-baseline.sql: the accepted notification
-- migrator (_grant_runtime_privileges in
-- services/api/app/notifications_truth/migrator.py) grants SELECT to the
-- configured runtime role on the five append-only relations plus
-- notification_recovery_park, and only revokes on the rest. Which role ends up
-- able to read notification_event, notification_delivery, notification_source,
-- push_subscription, notification_preference and shop_notification_policy is
-- therefore a property of how the notification slice was provisioned, not of
-- the inventory envelope. This file refuses to guess: N0 asserts the SELECT
-- grant on all twelve relations for the current session and fails closed,
-- naming what is missing, rather than producing a digest over a partial set.
--
-- A partial digest would be worse than no digest. If N0 stops, record the role
-- that does hold the grants in the audit template and rerun this file in that
-- session. Do not weaken N0 and do not drop relations from the list.
--
-- Output: r5_notification_digest, passed to 05b-r5-notification.sql and to
-- 07b-verify-notification.sql as -v base_r5_notification.

\ir lib-guards.sql

\echo '--- N0 the session can read all twelve notification relations ---'
-- Set taken verbatim from NOTIFICATION_TABLE_NAMES in
-- services/api/app/notifications_truth/models.py.
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
                WHERE has_table_privilege(current_user, 'public.' || required.rel,
                                          'SELECT')) = 12
         THEN current_user || '-can-read-all-12'
         ELSE current_setting('stashtab_f2.f2_notification_baseline_n0_session_lacks_select_on_a_notification_relation')
       END AS n0_notification_select_privileges;

\echo '--- N1 per-relation notification baseline ---'
WITH notification(rel, total_rows, cutover_shop_rows) AS (
  VALUES
    ('notification_audit',
     (SELECT count(*) FROM notification_audit),
     (SELECT count(*) FROM notification_audit WHERE shop_id = :'cutover_shop_id')),
    ('notification_delivery',
     (SELECT count(*) FROM notification_delivery),
     (SELECT count(*) FROM notification_delivery WHERE shop_id = :'cutover_shop_id')),
    ('notification_delivery_attempt',
     (SELECT count(*) FROM notification_delivery_attempt),
     (SELECT count(*) FROM notification_delivery_attempt WHERE shop_id = :'cutover_shop_id')),
    ('notification_event',
     (SELECT count(*) FROM notification_event),
     (SELECT count(*) FROM notification_event WHERE shop_id = :'cutover_shop_id')),
    ('notification_occurrence',
     (SELECT count(*) FROM notification_occurrence),
     (SELECT count(*) FROM notification_occurrence WHERE shop_id = :'cutover_shop_id')),
    ('notification_occurrence_transition',
     (SELECT count(*) FROM notification_occurrence_transition),
     (SELECT count(*) FROM notification_occurrence_transition WHERE shop_id = :'cutover_shop_id')),
    ('notification_preference',
     (SELECT count(*) FROM notification_preference),
     (SELECT count(*) FROM notification_preference WHERE shop_id = :'cutover_shop_id')),
    ('notification_recovery_park',
     (SELECT count(*) FROM notification_recovery_park),
     (SELECT count(*) FROM notification_recovery_park WHERE shop_id = :'cutover_shop_id')),
    ('notification_source',
     (SELECT count(*) FROM notification_source),
     (SELECT count(*) FROM notification_source WHERE shop_id = :'cutover_shop_id')),
    ('notification_source_observation',
     (SELECT count(*) FROM notification_source_observation),
     (SELECT count(*) FROM notification_source_observation WHERE shop_id = :'cutover_shop_id')),
    ('push_subscription',
     (SELECT count(*) FROM push_subscription),
     (SELECT count(*) FROM push_subscription WHERE shop_id = :'cutover_shop_id')),
    ('shop_notification_policy',
     (SELECT count(*) FROM shop_notification_policy),
     (SELECT count(*) FROM shop_notification_policy WHERE shop_id = :'cutover_shop_id'))
)
SELECT rel,
       total_rows,
       cutover_shop_rows,
       md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows, '|')
             OVER ()) AS r5_notification_digest
FROM notification
ORDER BY rel;

\echo '--- notification baseline complete ---'
