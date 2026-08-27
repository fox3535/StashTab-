# Scoring policy — intake/abstention

**Slice:** `card-resolution-core-v1 / slice-01-intake-abstention`  
**Status:** `FROZEN` under `STASHTAB-CARD-RESOLUTION-001` v1.0.0 §16  
**Ruleset id:** `identity-score-v0`  
**Authority:** D-032; contract §§1, 5, 6, 7, 8, 13.1, 15  
**Depends on:** D-030, D-031, D-032  
**JustTCG / TCGCSV:** disabled; not called; not identity resolvers  
**Implementation:** locked

This is frozen **policy detail**, not a contract amendment. Contract version
remains **1.0.0**. Unique exact local accept without an external request is
already authorized by §§5 and 13.1. The earlier planning remark about an
amendment applied only to **ambiguous-band** auto-accept without JustTCG.

## 1. Identity score

`S` uses exact identity evidence only.

Allowed: game, set name or set code, collector number, normalized name,
language, printing/finish.

Forbidden in `S` and in eligibility: price, TCGCSV/JustTCG price, market
rank, OCR-only guess, RapidFuzz/token similarity, agent narrative.

Fuzzy name similarity may **retrieve** candidates. It must not raise `S`
and cannot verify a card (D-031).

## 2. Integer formula (`identity-score-v0`)

Score in hundredths (integers 0–100). Auto-accept only at **100**.

```text
S_i =
  15 * exact(game)
+ 20 * exact(set_name or set_code)
+ 20 * exact(collector_number)
+ 25 * exact(normalized_name)
+ 10 * exact(language)
+ 10 * exact(printing)
```

`exact` is 1 only if both sides are present and equal after `norm-v0`.
Missing field → 0 for that term. The sum cannot replace a missing or
conflicting mandatory field (D-032.9).

Margin: `S_winner - S_runner_up >= 10` among **eligible** candidates
(D-032.11). No floating-point compare.

`price_confidence` is always null in this slice.

## 3. `norm-v0` (format only)

Versioned with this ruleset. No synonym expansion except the maps below.

| Field | Format-only rules |
|---|---|
| Name | Unicode NFKC, case-fold, collapse whitespace, strip punctuation except letters/digits/`#`. Do not drop tokens such as `ex` or `V`. |
| Set | NFKC, case-fold, collapse whitespace, strip `®`/`™`. `Base Set` ≠ `Base Set 2`. |
| Collector number | Trim. Do not equate `4` and `4/102`. Strip leading zeros only on a fully numeric value (`004` → `4`). `4a` ≠ `4`. |
| Language | NFKC, case-fold, trim, then **exact** lookup in `language-map-v0`. Unmapped text is not equal to any canonical language. |
| Printing | NFKC, case-fold, trim, then **exact** lookup in `printing-map-v0`. No fuzzy, price, or inferred printing. |

### `language-map-v0`

| Input (after format) | Canonical |
|---|---|
| `en`, `eng`, `english` | `en` |
| `ja`, `jp`, `jpn`, `japanese` | `ja` |
| `ko`, `kr`, `kor`, `korean` | `ko` |
| `zh-hans`, `zh-cn`, `chs`, `simplified chinese` | `zh-Hans` |
| `zh-hant`, `zh-tw`, `cht`, `traditional chinese` | `zh-Hant` |
| `fr`, `fra`, `french` | `fr` |
| `de`, `deu`, `german` | `de` |
| `es`, `spa`, `spanish` | `es` |
| `it`, `ita`, `italian` | `it` |
| `pt`, `por`, `portuguese` | `pt` |

Unlisted language strings do not match.

### `printing-map-v0`

| Input (after format) | Canonical |
|---|---|
| `non-holo`, `nonholo`, `normal`, `unlimited` | `non_holo` |
| `holo`, `holofoil`, `holographic` | `holo` |
| `reverse holo`, `reverse-holo`, `reverse holofoil` | `reverse_holo` |
| `full art`, `full-art` | `full_art` |
| `secret rare` | `secret_rare` |
| `promo` | `promo` |

Unlisted printing strings do not match. A named evidence printing makes
another candidate ineligible **only** when both sides map to canonical
ids and those ids differ (D-032.3). If evidence printing is unmapped,
treat as not exact; do not infer; usually **abstain**.

## 4. Game registry

Allowed games for this slice: **`pokemon` only** (canonical).

Caller **must** send game. After `norm-v0` (NFKC, case-fold): `pokemon`,
`pokémon`, `pokémon` → `pokemon`. No silent default.

- Missing game → **reject** (`missing_game`)
- Game not in registry → **reject** (`unsupported_game`)
- Evidence game `pokemon` but no eligible Pokemon candidate remains
  (including all remaining rows being another game) → **reject**
  (`game_mismatch`)

Stable-identifier clashes (two different JustTCG/TCGplayer ids on one
intake) still **abstain** (contract invariant 5: human review). That is
not a game-registry reject.

## 5. Eligibility and accept gates

**Eligible** candidate: same shop; same canonical game as evidence;
no mapped identity field conflicts with evidence.

**Plausible:** eligible and `S >= 70`.

Auto-**accept** only if all of:

1. Shop-verified caller; candidates scoped to that shop.
2. All six mandatory fields present on evidence and exact vs winner
   (`S = 100`).
3. Exactly one eligible canonical identity. Two DB rows matching all six
   fields → **abstain** (D-032.8).
4. Margin `>= 10` vs next eligible, or no runner-up.
5. No second plausible candidate.
6. JustTCG not called.

Omitted language or printing → **abstain**.  
Set/number vs name mismatch cannot be rescued by name: no accept. If
evidence is well-formed Pokemon and some eligible rows remain but none
reach `S = 100` uniquely → **abstain**. If no eligible row remains after
game-consistent filtering → **reject** only for game mismatch/unsupported;
otherwise **abstain**.

Timeout, scorer failure, empty catalog, provider unavailability, agent
disagreement → **abstain**, never accept.

## 6. State machine (this slice)

```text
received
  → rejected     if missing/unsupported game, malformed request, or other-shop-only candidates
  → abstained    if insufficient, duplicate identity, conflict-for-review, weak/ambiguous, or failure
  → accepted     if all auto-accept gates pass (identity only; not inventory)
```

Human `accept_identity` / `reject` on the review queue is later and still
must not write inventory.

## 7. Examples (M = 0.10, integer scores)

| ID | Evidence | Result | Why |
|---|---|---|---|
| E1 | Pokemon, Base, #4, Charizard, EN, Non-Holo; one row | accept | S=100, unique, margin n/a |
| E2 | Same plus Holo row; evidence printing maps to `non_holo` | accept | Holo canonical id differs → ineligible; not fuzzy |
| E3 | Same two rows; printing omitted | abstain | Omitted printing (D-032.2) |
| E4 | Name only; fuzzy pulls two Charizards | abstain | Retrieve only; S≪100 |
| E5 | E1 plus matching holo **price** | accept | Price ignored |
| E6 | Pokemon Base #4 named Blastoise | abstain | Name/number conflict; not rescued by name |
| E7 | Game One Piece (not in registry) | reject | Unsupported game |
| E8 | Game omitted | reject | Missing game; no Pokemon default |
| E9 | Game Pokemon; only One Piece rows | reject | Game mismatch, no eligible Pokemon identity |
| E10 | Empty body | reject | Malformed |
| E11 | Scorer throws | abstain | Failure is not success |
| E12 | Two DB rows identical on all six fields | abstain | Duplicate canonical identity |
| E13 | E1 replay same `intake_id` | same stored | Idempotent |
| E14 | Evidence printing `shiny` (unmapped) with holo and non-holo rows | abstain | No canonical printing match; no inference |

JustTCG and TCGCSV are not used. No inventory write in any row.

## 8. Freeze path

This policy is **FROZEN** as `identity-score-v0` under contract §16.
Manifest: `freezes/FREEZE-IDENTITY-SCORE-v0.json` (does not hash itself).
Implementation remains locked until a separate named unlock.
