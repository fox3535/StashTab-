# AI and analytics risk (planning)

Implementation blocked. No production models, prompt edits, or scheduled
training.

## Advisory boundary

Portfolio Watch and Market Watch **recommend**. They cannot list, price,
purchase, sell, transfer, or remove inventory. Card-resolution remains under
the frozen contract: AI agreement is not proof (contract §1, §6).

Do not describe predictions as guaranteed values.

## Separate confidences

Identity, price, liquidity, trend, and recommendation confidence stay
separate. Mixing them in one undocumented number is a defect.

## Tenant isolation of learning

One vendor’s acquisition costs, inventory, actions, and outcomes **cannot**
train or influence another vendor’s output without an explicit approved
anonymization and aggregation policy. Default: shop-scoped datasets only.

Production retrieval may use **current authorized data for that shop** plus
**approved** market observations. It may not pull another shop’s lots.

## No silent production learning

Production agents must not silently modify:

- prompts
- scoring weights
- thresholds
- data-source priorities
- training sets
- models
- blocking gates

## Governed outcome learning (offline)

1. Preserve the recommendation and evidence.
2. Record the vendor’s decision without treating it as ground truth.
3. Evaluate after the declared horizon.
4. Store the observed outcome in a labeled evaluation dataset.
5. Compare predicted and observed results.
6. Propose feature, rule, prompt, or model changes **offline**.
7. Run temporal holdout, leakage, tenant-isolation, manipulation,
   calibration, and regression evaluations.
8. Independent review and human approval before promotion.

## Evaluation hazards (must design against)

- Future information in point-in-time sets
- Survivorship bias
- Duplicate sales
- Stale pricing
- Condition mixing
- Variant mixing
- Source manipulation / low-volume pumps treated as signal
- Circular learning from the agent’s previous recommendations

## Card-resolution overlap

Do not let Market Watch override unresolved identity. Unresolved or
ambiguous cards never enter sellable inventory (frozen contract invariant 2).
Portfolio signals on unresolved identity must abstain.
