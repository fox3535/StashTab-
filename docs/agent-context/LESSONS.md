# Evidence-backed lessons

- Agent agreement is not correctness evidence. Use contract clauses, tests, and
  repository facts. Source: contract sections 12 and 13.
- An agent's discomfort is not a JustTCG trigger. Use deterministic confidence,
  stable identifiers, cache state, and budgets. Source: contract section 6.
- Large raw histories increase drift. Fresh agents should receive only CURRENT,
  the relevant role packet, and cited supporting records. Source: D-001.
- Applying inventory schema to staging is not route enablement. Search
  already exists and is not mutation-gated; writes stay 503 until cutover
  is complete. Do not treat empty-table reads as an unlock. Source: D-028;
  D-029; `PLAN-SLICE-03-INVENTORY-READONLY-SEARCH.md`.
- An empty inventory cannot fully prove PATCH or checkout write guards.
  Record those probes unused; do not seed merely to finish them. Source:
  D-029.
- Notification delivery must not influence card workflow outcomes. Source:
  proposed amendment 1.1.0, invariant 5.
- RapidFuzz ≥80 is not verified identity. Upstream JustTCG/TCGCSV catalog
  price sync is not an identity fallback. Source: D-031.
