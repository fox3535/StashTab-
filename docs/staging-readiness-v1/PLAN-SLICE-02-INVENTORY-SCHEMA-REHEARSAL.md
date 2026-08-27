# Proposed checkpoint — slice-02 inventory schema rehearsal

**Slice:** `staging-readiness-v1 / slice-02-inventory-schema-rehearsal`  
**Status:** `PLANNING ONLY — NOT APPROVED, NOT UNLOCKED, NOT EXECUTED`  
**Depends on:** slice-01 identity smoke accepted on staging (`ACCEPTANCE-SLICE-01.md`)

This is a proposal. Do not run migrators, create inventory tables, enable dual-write, or change Railway/Neon until a named human unlock.

## Intent

Rehearse inventory-truth schema work against **synthetic staging only**, after shops/memberships already exist. Follow frozen `REHEARSAL.md` track A ideas without treating that freeze as authorization.

## Proposed bounds (if later approved)

- Target: existing isolated staging Neon, not production
- Rehearse inventory-truth migrator on empty-of-inventory staging (identity tables already present)
- Prove second run is a no-op
- Prove injected failure rolls back with no leftover truth tables
- Keep notifications, worker, Shopify, Web Push, and dual-write **off**
- Do not load production data
- Do not enable receive/POS/adjust routes

## Explicitly out of scope

- Production schema apply
- Notification schema
- Worker process
- Shopify sandbox
- Cutover / recon against live inventory
- Frontend inventory UI changes
- Unlocking `CSV-COST-FEEDBACK-GATE`

## Entry required before execution

A later named human unlock that cites this file, names the operator, and states the exact Neon database. Until then, agents must not start slice-02.
