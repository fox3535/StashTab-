"""Frozen identity-score-v0. Integer hundredths. Fuzzy retrieve never raises S."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

RULESET_VERSION = "identity-score-v0"
CONTRACT_VERSION = "1.0.0"
GAME_REGISTRY = frozenset({"pokemon"})
MARGIN_HUNDREDTHS = 10
ACCEPT_TOTAL = 100
PLAUSIBLE_FLOOR = 70
FUZZY_RETRIEVE_FLOOR = 80

WEIGHTS = {
    "game": 15,
    "set": 20,
    "collector_number": 20,
    "normalized_name": 25,
    "language": 10,
    "printing": 10,
}

LANGUAGE_MAP = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "ja": "ja",
    "jp": "ja",
    "jpn": "ja",
    "japanese": "ja",
    "ko": "ko",
    "kr": "ko",
    "kor": "ko",
    "korean": "ko",
    "zh-hans": "zh-Hans",
    "zh-cn": "zh-Hans",
    "chs": "zh-Hans",
    "simplified chinese": "zh-Hans",
    "zh-hant": "zh-Hant",
    "zh-tw": "zh-Hant",
    "cht": "zh-Hant",
    "traditional chinese": "zh-Hant",
    "fr": "fr",
    "fra": "fr",
    "french": "fr",
    "de": "de",
    "deu": "de",
    "german": "de",
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "it": "it",
    "ita": "it",
    "italian": "it",
    "pt": "pt",
    "por": "pt",
    "portuguese": "pt",
}

PRINTING_MAP = {
    "non-holo": "non_holo",
    "nonholo": "non_holo",
    "normal": "non_holo",
    "unlimited": "non_holo",
    "holo": "holo",
    "holofoil": "holo",
    "holographic": "holo",
    "reverse holo": "reverse_holo",
    "reverse-holo": "reverse_holo",
    "reverse holofoil": "reverse_holo",
    "full art": "full_art",
    "full-art": "full_art",
    "secret rare": "secret_rare",
    "promo": "promo",
}


class ScoringTimeout(Exception):
    """Injected or wall-clock scoring timeout."""


class ScoringFailure(Exception):
    """Scorer crashed. Callers must abstain."""


def _blank_to_none(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def normalize_game(value: object | None) -> str | None:
    formatted = _format_text(value)
    if not formatted:
        return None
    compact = formatted.replace(" ", "")
    compact = compact.replace("pokémon", "pokemon").replace("pokèmon", "pokemon")
    if compact == "pokemon":
        return "pokemon"
    return compact


def normalize_name(value: object | None) -> str | None:
    formatted = _format_text(value)
    if not formatted:
        return None
    kept: list[str] = []
    for char in formatted:
        if char.isalnum() or char == "#" or char.isspace():
            kept.append(char)
        else:
            kept.append(" ")
    collapsed = re.sub(r"\s+", " ", "".join(kept)).strip()
    return collapsed or None


def normalize_set(value: object | None) -> str | None:
    formatted = _format_text(value)
    if not formatted:
        return None
    formatted = formatted.replace("®", "").replace("™", "").replace("(tm)", "")
    formatted = re.sub(r"\s+", " ", formatted).strip()
    return formatted or None


def normalize_collector_number(value: object | None) -> str | None:
    if value is None:
        return None
    raw = unicodedata.normalize("NFKC", str(value)).strip()
    if not raw:
        return None
    if raw.isdigit():
        return str(int(raw))
    return raw


def normalize_language(value: object | None) -> str | None:
    formatted = _format_text(value)
    if not formatted:
        return None
    return LANGUAGE_MAP.get(formatted)


def normalize_printing(value: object | None) -> str | None:
    formatted = _format_text(value)
    if not formatted:
        return None
    return PRINTING_MAP.get(formatted)


def identity_key(
    game: str | None,
    set_name: str | None,
    set_code: str | None,
    collector_number: str | None,
    name: str | None,
    language: str | None,
    printing: str | None,
) -> str:
    return "|".join(
        [
            game or "",
            set_name or "",
            set_code or "",
            collector_number or "",
            name or "",
            language or "",
            printing or "",
        ]
    )


def _optional_id(value: object | None) -> str | None:
    return _blank_to_none(value)


@dataclass(frozen=True)
class Evidence:
    game: str | None
    name: str | None
    set_name: str | None
    set_code: str | None
    collector_number: str | None
    language: str | None
    printing: str | None
    justtcg_id: str | None = None
    tcgplayer_id: str | None = None
    price: object | None = None
    model_confidence: object | None = None
    advisory_note: str | None = None

    @classmethod
    def from_payload(cls, payload: dict) -> Evidence:
        return cls(
            game=payload.get("game"),
            name=payload.get("name"),
            set_name=payload.get("set_name"),
            set_code=payload.get("set_code"),
            collector_number=payload.get("collector_number"),
            language=payload.get("language"),
            printing=payload.get("printing"),
            justtcg_id=_optional_id(payload.get("justtcg_id")),
            tcgplayer_id=_optional_id(payload.get("tcgplayer_id")),
            price=payload.get("price"),
            model_confidence=payload.get("model_confidence"),
            advisory_note=payload.get("advisory_note"),
        )


@dataclass(frozen=True)
class Candidate:
    shop_id: str
    game: str | None
    name: str | None
    set_name: str | None
    set_code: str | None
    collector_number: str | None
    language: str | None
    printing: str | None
    justtcg_id: str | None = None
    tcgplayer_id: str | None = None
    source: str = "catalog"
    row_id: str | None = None

    @property
    def canonical_game(self) -> str | None:
        return normalize_game(self.game)

    @property
    def key(self) -> str:
        return identity_key(
            self.canonical_game,
            normalize_set(self.set_name),
            normalize_set(self.set_code),
            normalize_collector_number(self.collector_number),
            normalize_name(self.name),
            normalize_language(self.language),
            normalize_printing(self.printing),
        )


@dataclass
class ScoredCandidate:
    candidate: Candidate
    total: int
    components: dict[str, int]
    eligible: bool
    plausible: bool
    retrieved_via_fuzzy: bool
    identity_key: str


@dataclass
class Decision:
    result: str
    state: str
    reason_codes: list[str]
    winner: ScoredCandidate | None
    scored: list[ScoredCandidate]
    identity_confidence_hundredths: int | None
    decision_source: str | None = "rules_local"


def _exact(left: str | None, right: str | None) -> bool:
    return bool(left and right and left == right)


def _fuzzy_name_ratio(left: str | None, right: str | None) -> int:
    if not left or not right:
        return 0
    try:
        from rapidfuzz import fuzz
    except ImportError:
        from difflib import SequenceMatcher

        return int(SequenceMatcher(None, left, right).ratio() * 100)
    return int(fuzz.WRatio(left, right))


def retrieve_candidates(
    catalog: list[Candidate],
    request_candidates: list[Candidate],
    shop_id: str,
) -> tuple[list[Candidate], list[str]]:
    if any(row.shop_id != shop_id for row in request_candidates):
        return [], ["other_shop_candidate"]
    merged: list[Candidate] = []
    seen: set[tuple[str, str | None]] = set()
    for row in list(catalog) + list(request_candidates):
        if row.shop_id != shop_id:
            continue
        marker = (row.key, row.row_id)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(row)
    return merged, []


def score_candidate(evidence: Evidence, candidate: Candidate) -> ScoredCandidate:
    e_game = normalize_game(evidence.game)
    e_set_name = normalize_set(evidence.set_name)
    e_set_code = normalize_set(evidence.set_code)
    e_number = normalize_collector_number(evidence.collector_number)
    e_name = normalize_name(evidence.name)
    e_lang = normalize_language(evidence.language)
    e_print = normalize_printing(evidence.printing)

    c_game = candidate.canonical_game
    c_set_name = normalize_set(candidate.set_name)
    c_set_code = normalize_set(candidate.set_code)
    c_number = normalize_collector_number(candidate.collector_number)
    c_name = normalize_name(candidate.name)
    c_lang = normalize_language(candidate.language)
    c_print = normalize_printing(candidate.printing)

    set_exact = _exact(e_set_name, c_set_name) or _exact(e_set_code, c_set_code)
    components = {
        "game": WEIGHTS["game"] if _exact(e_game, c_game) else 0,
        "set": WEIGHTS["set"] if set_exact else 0,
        "collector_number": WEIGHTS["collector_number"] if _exact(e_number, c_number) else 0,
        "normalized_name": WEIGHTS["normalized_name"] if _exact(e_name, c_name) else 0,
        "language": WEIGHTS["language"] if _exact(e_lang, c_lang) else 0,
        "printing": WEIGHTS["printing"] if _exact(e_print, c_print) else 0,
    }
    total = sum(components.values())
    retrieved_via_fuzzy = _fuzzy_name_ratio(e_name, c_name) >= FUZZY_RETRIEVE_FLOOR and not _exact(
        e_name, c_name
    )
    eligible = True
    if e_game and c_game and e_game != c_game:
        eligible = False
    if e_lang and c_lang and e_lang != c_lang:
        eligible = False
    if e_print and c_print and e_print != c_print:
        eligible = False
    return ScoredCandidate(
        candidate=candidate,
        total=total,
        components=components,
        eligible=eligible,
        plausible=eligible and total >= PLAUSIBLE_FLOOR,
        retrieved_via_fuzzy=retrieved_via_fuzzy,
        identity_key=candidate.key,
    )


def _six_fields_present(evidence: Evidence) -> bool:
    return all(
        [
            normalize_game(evidence.game),
            normalize_set(evidence.set_name) or normalize_set(evidence.set_code),
            normalize_collector_number(evidence.collector_number),
            normalize_name(evidence.name),
            _format_text(evidence.language) is not None and normalize_language(evidence.language) is not None,
            _format_text(evidence.printing) is not None and normalize_printing(evidence.printing) is not None,
        ]
    )


def _language_omitted(evidence: Evidence) -> bool:
    return _format_text(evidence.language) is None


def _printing_omitted(evidence: Evidence) -> bool:
    return _format_text(evidence.printing) is None


def _identifier_conflict(evidence: Evidence, scored: list[ScoredCandidate]) -> bool:
    e_just = _optional_id(evidence.justtcg_id)
    e_tcg = _optional_id(evidence.tcgplayer_id)
    just_keys = {
        row.identity_key
        for row in scored
        if e_just and _optional_id(row.candidate.justtcg_id) == e_just
    }
    tcg_keys = {
        row.identity_key
        for row in scored
        if e_tcg and _optional_id(row.candidate.tcgplayer_id) == e_tcg
    }
    if e_just and e_tcg and just_keys and tcg_keys and just_keys != tcg_keys:
        return True
    matched = set()
    if e_just:
        matched |= just_keys
    if e_tcg:
        matched |= tcg_keys
    return len(matched) > 1


def decide(evidence: Evidence, candidates: list[Candidate]) -> Decision:
    game = normalize_game(evidence.game)
    if game is None:
        return Decision(
            result="rejected",
            state="rejected",
            reason_codes=["missing_game"],
            winner=None,
            scored=[],
            identity_confidence_hundredths=None,
        )
    if game not in GAME_REGISTRY:
        return Decision(
            result="rejected",
            state="rejected",
            reason_codes=["unsupported_game"],
            winner=None,
            scored=[],
            identity_confidence_hundredths=None,
        )

    scored = [score_candidate(evidence, row) for row in candidates]
    eligible = [row for row in scored if row.eligible]
    pokemon_eligible = [row for row in eligible if row.candidate.canonical_game == "pokemon"]
    other_games = [row for row in candidates if row.canonical_game and row.canonical_game != "pokemon"]

    if _identifier_conflict(evidence, scored):
        return Decision(
            result="abstained",
            state="pending_human_review",
            reason_codes=["identifier_conflict"],
            winner=None,
            scored=scored,
            identity_confidence_hundredths=None,
        )

    if not pokemon_eligible and other_games:
        return Decision(
            result="rejected",
            state="rejected",
            reason_codes=["game_mismatch"],
            winner=None,
            scored=scored,
            identity_confidence_hundredths=None,
        )

    if _language_omitted(evidence) or _printing_omitted(evidence):
        codes = []
        if _language_omitted(evidence):
            codes.append("omitted_language")
        if _printing_omitted(evidence):
            codes.append("omitted_printing")
        return Decision(
            result="abstained",
            state="pending_human_review",
            reason_codes=codes,
            winner=None,
            scored=scored,
            identity_confidence_hundredths=max((row.total for row in eligible), default=None),
        )

    if not pokemon_eligible:
        return Decision(
            result="abstained",
            state="pending_human_review",
            reason_codes=["insufficient_evidence"],
            winner=None,
            scored=scored,
            identity_confidence_hundredths=None,
        )

    perfect = [row for row in pokemon_eligible if row.total == ACCEPT_TOTAL]
    unique_keys = {row.identity_key for row in perfect}
    if len(perfect) >= 2 and len(unique_keys) == 1:
        return Decision(
            result="abstained",
            state="pending_human_review",
            reason_codes=["duplicate_canonical_identity"],
            winner=None,
            scored=scored,
            identity_confidence_hundredths=ACCEPT_TOTAL,
        )
    if len(unique_keys) > 1:
        ranked = sorted(perfect, key=lambda row: row.total, reverse=True)
        return Decision(
            result="abstained",
            state="pending_human_review",
            reason_codes=["ambiguous_identity"],
            winner=ranked[0] if ranked else None,
            scored=scored,
            identity_confidence_hundredths=ranked[0].total if ranked else None,
        )

    ranked_eligible = sorted(pokemon_eligible, key=lambda row: row.total, reverse=True)
    winner = ranked_eligible[0]
    runner_up = ranked_eligible[1] if len(ranked_eligible) > 1 else None
    margin = winner.total - (runner_up.total if runner_up else 0)
    plausible = [row for row in pokemon_eligible if row.plausible]

    if (
        _six_fields_present(evidence)
        and winner.total == ACCEPT_TOTAL
        and len(unique_keys) == 1
        and margin >= MARGIN_HUNDREDTHS
        and len(plausible) <= 1
    ):
        return Decision(
            result="accepted",
            state="accepted",
            reason_codes=["unique_exact_identity"],
            winner=winner,
            scored=scored,
            identity_confidence_hundredths=winner.total,
        )

    if winner.total == ACCEPT_TOTAL and runner_up and margin < MARGIN_HUNDREDTHS:
        return Decision(
            result="abstained",
            state="pending_human_review",
            reason_codes=["insufficient_margin"],
            winner=winner,
            scored=scored,
            identity_confidence_hundredths=winner.total,
        )

    codes = ["insufficient_evidence"]
    if winner.components["normalized_name"] == 0 and (
        winner.components["set"] or winner.components["collector_number"]
    ):
        codes = ["name_number_conflict"]
    return Decision(
        result="abstained",
        state="pending_human_review",
        reason_codes=codes,
        winner=winner,
        scored=scored,
        identity_confidence_hundredths=winner.total,
    )
