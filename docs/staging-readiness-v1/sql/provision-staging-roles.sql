-- Staging Neon role bootstrap (idempotent).
-- Execute only as the Neon project owner (or with explicit owner authorization).
-- Do not run from API or worker. Do not run against production.
-- Passwords are set by the operator outside this file; never commit secrets.

-- Roles: NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
-- Runtime must not be GRANT-ed the migrator role.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stashtab_migrator') THEN
    CREATE ROLE stashtab_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stashtab_api') THEN
    CREATE ROLE stashtab_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stashtab_worker') THEN
    CREATE ROLE stashtab_worker LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stashtab_readonly') THEN
    CREATE ROLE stashtab_readonly LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END
$$;

ALTER ROLE stashtab_migrator NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE stashtab_api NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE stashtab_worker NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE stashtab_readonly NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

REVOKE stashtab_migrator FROM stashtab_api;
REVOKE stashtab_migrator FROM stashtab_worker;
REVOKE stashtab_migrator FROM stashtab_readonly;
REVOKE stashtab_api FROM stashtab_worker;
REVOKE stashtab_worker FROM stashtab_api;

-- Operator substitutes the staging database name. Never a production database.
-- GRANT CONNECT ON DATABASE <staging_db> TO stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly;
GRANT USAGE ON SCHEMA public TO stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM stashtab_api, stashtab_worker, stashtab_readonly;

-- Table ownership and DML grants are applied after legacy bootstrap / migrator runs.
-- Runtime LOGIN proof (required before truth/notification apply):
--   SET ROLE stashtab_migrator  -- must fail as stashtab_api
--   CREATE TABLE / ALTER TABLE / CREATE ROLE  -- must fail as stashtab_api
