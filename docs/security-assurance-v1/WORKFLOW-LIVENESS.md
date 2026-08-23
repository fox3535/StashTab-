# Workflow-liveness contract

## Precedence

1. Safety and law  
2. Frozen workflow contract (**frozen** amendments only)  
3. Explicit human approvals  
4. Current phase gate  
5. Assigned task  
6. Role-specific guidance  
7. General preferences  

## One adjudicator per gate

| Gate id | Adjudicator |
|---|---|
| `independent_review` | Human ≠ planner |
| `planning_accept` | Executive sponsor |
| `implementation_unlock` | Executive sponsor |
| `pr_passive` | Application control owner (CI validates) |
| `weekly_window` | Operations owner |
| `pre_release` | Security reviewer (human) |
| `quarterly_exercise` | Operations owner |
| `pentest` | Executive sponsor |
| `learning` | Security reviewer; one wait per `learning:<fingerprint>` |
| `payments_config` | Executive sponsor (provider + counsel letters are evidence) |
| `pci_scope` | Executive sponsor (PCI specialist letter is evidence) |
| `tax_allocation` | Executive sponsor (tax counsel/accountant letter is evidence) |
| `accounting_review` | Executive sponsor (accountant letter is evidence) |
| `market_data_license` | Executive sponsor (license/legal letter is evidence) |
| `watch_model_promote` | Executive sponsor (independent review is evidence) |
| `cross_tenant_aggregate` | Executive sponsor (privacy/legal letter is evidence) |
| `card_resolution_freeze` | Existing contract release human |

Legal/license/PCI/COGS/production-migration letters are **deferred
professional gates**. They do **not** unlock code and they do **not** block
`planning_accept`. Production go-live of those slices still needs the
matching letter plus `implementation_unlock`.

## Deterministic completion

Valid transition only if the idempotency key is unique for that gate_id +
run, required evidence exists, and status/actor/timestamp/evidence refs are
written once. Agents must not mark `completed`. Timeout is never success.

Deadlock → `failed_permanent` (terminal). A human may later issue a **new**
key for `awaiting_named_human`. The machine must not auto-escalate.

| Fingerprint | Signal |
|---|---|
| Repeated failure | Same error class three times with no artifact change |
| No new evidence | Review cites only prior review IDs |
| Expired heartbeat | Missed interval on a **working** state |
| Repeated approval | Same `gate_id` question twice, unchanged packet |
| Prohibited action | Scan/attack/migrate/pay/train/push/enable jobs |
| Unchanged reviews | Same SHA, identical reviews |
| Exhausted budget | Time box, attempt count, or token/step budget |
| Revisit without change | Same state + same evidence hash + **same attempt** |

Retry uses `retry_wait` with incremented `attempt`, not a blind return to the
same key. Human-wait does not heartbeat-complete.

## Implementation unlock

State `implementation_unlock`. Named slice only. No silent wait. Watch
promotion still needs this if it adds schema or jobs.
