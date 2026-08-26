# Database roles

**Gate:** `MIGRATOR-ROLE-PROVISIONING-GATE` stays **open** until proven on the **staging** Neon with real LOGIN, not pytest `SET ROLE`.

## Approved ownership

Neon project owner (or explicit delegate) runs `sql/provision-staging-roles.sql` once. API/worker never create roles. `STASHTAB_TRUTH_MIGRATOR_ROLE` stays unset on runtime services.

## Roles

| Role | Login | Purpose |
| --- | --- | --- |
| `stashtab_migrator` | Named migration jobs only | Owns tables. Runs truth and notification migrators later. |
| `stashtab_api` | API `DATABASE_URL` | DML only. No CREATE/ALTER/DROP/TRUNCATE on append-only truth/notification tables. |
| `stashtab_worker` | Worker URL later | DML only. Never DDL. |
| `stashtab_readonly` | Support | SELECT only. |

All: `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT`. Do not `GRANT migrator TO api`. Table owner is the migrator, not the API user.

## Forbidden

Inventory migrator may `CREATE ROLE` if `STASHTAB_TRUTH_MIGRATOR_ROLE` is set and missing. Do not use that path. Notification migrator already fails closed if a named runtime role is missing.

## Proof runtime cannot become migrator

Connect **as** `stashtab_api` (real LOGIN):

1. `SET ROLE stashtab_migrator` fails.
2. Not a member of the migrator role.
3. `rolsuper` / `rolcreaterole` false.
4. `CREATE TABLE` / `ALTER TABLE` / `DROP TRIGGER` fail.
5. `SET session_replication_role = replica` fails.
6. Same after a second migrator run.

## Credentials

Migrator: short-lived, operator-held, rotated after each apply, never in Railway API/worker. Revoke by rotating Neon passwords and removing Railway env, then restart.
