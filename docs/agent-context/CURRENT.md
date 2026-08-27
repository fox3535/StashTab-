# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-27
**Branch:** `feature/slice-01-authenticated-shell-read-inventory` from `main`
`af72bac501cd9c42b70cd0347f778db388c8c943`
**Staging API:** Railway deploy `17aeb85f-053f-4e5a-8d68-6d040d03c238` at Git SHA `0dd8f00b8d510b82e3d717a9570c0bc387e0479b`

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.1 and 1.1.2 frozen.
  Web Push off. Local 1.1.2 backend on `main` as `c3647a4`; not in production.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — frozen. Slices 01–03 on `main`
  via `c3647a4`. Staging schema applied 2026-08-27 (D-028). Not production.

## Current phase

`frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`
**Status:** `COMPLETED LOCALLY — NOT MERGED — NOT DEPLOYED — LIVE STAGING SMOKE PENDING` (D-038).
F0 exit remains passed for frontend recovery (D-035). Memberships read is
on `main` via PR #15 (D-037), not deployed to staging hosting.

Writes, worker, Shopify, notifications, Watch remain off. Convex is out (D-024).

## Approved boundaries

- Python/FastAPI owns business logic; tenant data uses `shop_id`.
- Identity: signed token + membership. Shop header is an untrusted hint.
- Partner Python is `vendor/mimir-partner/`; inspect, do not copy blindly.
- Humans approve writes, Web Push, payments, Watch, and later slices.

## Active gates

1. Identity smoke: **closed** (D-025).
2. Inventory schema on staging: **closed** (D-028).
3. Inventory read smoke: **closed** (D-029). Writes still off.
4. Production schema apply blocked.
5. Card-resolution intake/abstention: **merged, feature off** (D-034 / PR #13).
6. F0 exit for frontend recovery: **passed** (D-035).
7. My-shop memberships read: **merged on `main` via PR #15** (D-037). Not hosted on staging.
8. F1 slice-01 shell + read inventory: **completed locally** (D-038). Not merged.
   Later staging-smoke: real Clerk memberships, live staging inventory, full
   keyboard walkthrough.

## Next queued phases

1. Review/merge slice-01 draft PR, then a separate staging API deploy and smoke.
2. Later enablement, not F0: inventory write staging smoke, notification
   staging apply, production restore drill.
3. Do not enable card-resolution, writes, or push without a named unlock.
