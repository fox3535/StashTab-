# Bounded review — scoring policy proposal

**Target:** `SCORING-POLICY-INTAKE-ABSTENTION.md`  
**Pin:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**Budget:** one review, one correction. Not a freeze.

## Findings

| Lens | Result |
|---|---|
| Architecture | Identity-only `S`; FastAPI remains authority; providers deferred. |
| Integrity | Binary weights imply auto-accept only at `S = 1.00`. Must be explicit so owners are not surprised that 0.95 never appears. |
| Eligibility vs margin | Without “conflict excludes printing siblings,” E2 would always abstain and `M` would barely matter. That rule is the real policy choice. |
| Security | Cross-shop candidates ineligible. No provider calls. |
| Adversarial | Price cannot boost `S` (E5). Fuzzy name-only cannot accept (E4). |
| AI quality | RapidFuzz ≥80 rejected (D-031). Agents cannot accept. |
| Liveness | Failure → abstain (E10). No JustTCG hang. |

## Correction applied

- Stated that `S >= 0.95` ≡ `S = 1.00` under these weights.
- Split **eligible** (no field conflict) vs **plausible** (`S >= 0.70`).
- E2 vs E3 shows omitted vs supplied printing.
- PLAN-SLICE-01 no longer treats `M = 0.05` as the implied default; owner picks `M`.
- JustTCG described only as a future spike, not a resolver.

No further review loop.
