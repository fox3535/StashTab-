# Gate pointer — F1 slice-01 authenticated shell (additive)

Frozen `GATES.md` is unchanged. This pointer records frontend-recovery evidence.

**Local slice-01 shell + read-only inventory:** **completed locally** 2026-08-27.  
Evidence: `ACCEPTANCE-SLICE-01-AUTHENTICATED-SHELL-READ-INVENTORY.md`. D-038.

**Slice-01 merged, deployed staging smoke passed:** **accepted** 2026-08-27 (D-039).  
Frontend merged on `main` `3c3ca33` (PR #16, PR #17). Staging API deploy
`9c47945a`. Frontend tested locally at `http://localhost:3001`, not
deployed. Real Clerk membership loaded; Smoke Shop B auto-selected;
read-only inventory honest empty state; sign-out/re-sign-in, keyboard,
and mobile checks passed; deferred features locked; no schema or data
writes.

Staging-smoke gates now closed:

- Real Clerk membership loading on staging — passed
- Live staging inventory read through the new shell — passed
- Full keyboard walkthrough of the authenticated shell — passed
- Memberships route on staging hosting — passed via deploy `9c47945a`

Open backlog (non-blocking): bare `/admin/shopify` 404 gets an honest Not
Ready route in a later navigation/deferred-routes cleanup.

Writes, Shopify, notifications, payments, Watch, and Web Push stay off.
