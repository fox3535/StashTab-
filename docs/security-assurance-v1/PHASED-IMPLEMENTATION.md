# Proposed phased implementation order

**Status:** proposal. No slice auto-starts.

Canonical dependency order is
`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md` (D-007). This file only
maps security, accounting, and Watch **gates** onto those slices. Do not
treat this file as a second product roadmap.

Reuse-before-build: extend live FastAPI models. Do not start a parallel
inventory, sales, show, pricing, recon, Shopify, or Watch subsystem.

## Phase 0 — Planning

This directory + independent reviews. Exit: sponsor `planning_accept`
(typically `completed_with_warnings`). Does not unlock code.

## Roadmap A — Card identity (`card-resolution-core-v1`)

Owned by the card-resolution backlog. Notification checkpoint and frozen
contract gates first. Unfinished SOC 2 / payments / Watch **must not**
block it (D-004 still proposed).

## Roadmap B — `inventory-truth-foundation`

Plan: `docs/inventory-truth-v1/` (planning review required). Requires
`implementation_unlock` after fail-closed identity.

## Roadmap C — `vendor-financial-operations`

Requires `implementation_unlock`. Extend `Sale` with a parent receipt
(D-008), plus `PendingTrade` / `ShowSession` cash sessions and subledger.
Preserve show P&L until ledger-derived results match. Accounting support,
not a GL. Webhook **fixtures** only until `payments_config` + `pci_scope`.
Legal letters do not start this slice.

## Roadmap D — `market-data-foundation`

Requires `implementation_unlock` **and** `market_data_license`.

## Roadmap E — `deterministic-watch`

Requires `implementation_unlock`. Auditable metrics and abstention only.
No agent narratives. No inventory writes.

## Roadmap F — `governed-advisory-agents`

Requires `implementation_unlock`. Evidence-citing sell/hold/watch.
`watch_model_promote` is confirmation only until unlock.

## Security program slices (orthogonal)

Database hardening, passive PR jobs, signed staging windows, SOC 2 Type I
evidence — each needs its own unlock.

## Withdrawn

Consumer marketplace, meetup, multi-vendor cart, marketplace shipping,
seller payouts, escrow, buyer protection.
