# Superseded harness — combined PostgreSQL invocation

**Status:** `SUPERSEDED — NOT A PRODUCT DEFECT`  
**When:** 2026-08-27 local acceptance verification  
**Do not delete this record.**

A single combined pytest run launched card-resolution PostgreSQL tests,
inventory live-schema rehearsal, inventory-truth acceptance, and
notification PostgreSQL suites together. It failed.

Cause:

1. Card-resolution rehearsal applied through the superuser connection,
   so privilege normalization on truth tables was denied.
2. Older inventory-truth and notification suites read `STASHTAB_PG_URL`
   and targeted local port 55432, which was not running.

This is harness coupling, not a slice defect. Later separated runs on
fresh PostgreSQL 16 containers and a disposable `stashtab_it` database
passed and supersede this attempt.
