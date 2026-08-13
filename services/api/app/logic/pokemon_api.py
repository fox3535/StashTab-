"""Pokemon TCG API client — full parity with partner api_client.py (httpx)."""

from __future__ import annotations

import re
import time

import httpx
from rapidfuzz import fuzz

from app.config import settings


class SemanticResolver:
    """
    Maps user/OCR set names to official API set names and multi-pass fallback search.
    """

    PROMO_MAP = {
        "Mega Evolution Promos": "Mega Evolution Black Star Promos",
        "Mega Evolutions Promo": "Mega Evolution Black Star Promos",
        "First Partner Promos": "First Partner Promos",
    }

    def __init__(self, api_client: PokemonAPI) -> None:
        self.api_client = api_client

    def resolve_set_name(self, set_name: str) -> str:
        if not set_name:
            return set_name
        for user_set, official_set in self.PROMO_MAP.items():
            if user_set.lower() == set_name.lower():
                return official_set
        return set_name

    def fallback_search(
        self,
        set_name: str,
        number: str,
        name: str | None,
        pass_num: int = 1,
    ) -> dict | None:
        resolved_set = self.resolve_set_name(set_name)
        clean_number = self.api_client._sanitize_sequence_number(number)
        is_pokemon_generic = (
            resolved_set.lower() == "pokemon" if resolved_set else False
        )

        if pass_num == 1:
            if is_pokemon_generic:
                if name and name != "Unknown":
                    query = f'name:"{name}" number:"{clean_number}"'
                else:
                    query = f'number:"{clean_number}"'
            else:
                query = f'set.name:"{resolved_set}" number:"{clean_number}"'
            cards = self.api_client._query_api(query, page_size=5)
            if cards:
                return self.api_client._extract_card_result(cards[0])
            return self.fallback_search(set_name, number, name, pass_num=2)

        if pass_num == 2:
            if not name or name == "Unknown":
                return self.fallback_search(set_name, number, name, pass_num=3)
            query = f'name:"{name}"'
            cards = self.api_client._query_api(query, page_size=5)
            if cards:
                return self.api_client._extract_card_result(cards[0])
            return self.fallback_search(set_name, number, name, pass_num=3)

        if pass_num == 3:
            if not name or name == "Unknown":
                return None
            query = f'name:"{name}"'
            cards = self.api_client._query_api(query, page_size=250)
            if cards:
                for card in cards:
                    card_num = card.get("number", "")
                    if (
                        self.api_client._sanitize_sequence_number(card_num)
                        == clean_number
                    ):
                        return self.api_client._extract_card_result(card)
            return None

        return None


class PokemonAPI:
    """Client for the Pokemon TCG API (https://api.pokemontcg.io/v2)."""

    BASE_URL = "https://api.pokemontcg.io/v2/cards"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "pokemon_tcg_api_key", "") or None
        self.headers = {"User-Agent": "StashTab/1.0"}
        if self.api_key:
            self.headers["X-Api-Key"] = self.api_key
        self.resolver = SemanticResolver(self)

    @staticmethod
    def _sanitize_sequence_number(sequence_number: str) -> str:
        raw = sequence_number.strip().replace("O", "0").replace("o", "0")
        match = re.search(r"(\d+)", raw)
        if not match:
            return raw
        return match.group(1).lstrip("0") or "0"

    def _extract_set_keywords(self, set_name: str) -> list[str]:
        cleaned = re.sub(r"[:'\"!@#$%^*(){}[\]|\\<>~`]", " ", set_name)
        tokens = re.split(r"[\s&]+", cleaned)
        noise = {
            "sv",
            "swsh",
            "sm",
            "xy",
            "bw",
            "dp",
            "ex",
            "the",
            "of",
            "and",
            "a",
            "",
        }
        keywords = [t for t in tokens if t.lower() not in noise and len(t) > 1]
        if not keywords:
            keywords = [t for t in tokens if t.strip()]
        return keywords

    def _query_api(self, query: str, page_size: int = 5) -> list[dict]:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=8.0) as client:
                    resp = client.get(
                        self.BASE_URL,
                        params={"q": query, "pageSize": page_size},
                        headers=self.headers,
                    )
                    resp.raise_for_status()
                    return resp.json().get("data", [])
            except (httpx.TimeoutException, httpx.HTTPError):
                if attempt < max_attempts - 1:
                    time.sleep(1 if attempt == 0 else 2)
                else:
                    return []
            except Exception:
                return []
        return []

    def _extract_card_result(self, card: dict) -> dict:
        market_price = None
        tcgplayer = card.get("tcgplayer", {}) or {}
        prices = tcgplayer.get("prices", {}) or {}
        rate = float(getattr(settings, "usd_to_cad_rate", 1.43) or 1.43)
        if prices:
            for category in (
                "normal",
                "holofoil",
                "reverseHolofoil",
                "unlimitedHolofoil",
                "1stEditionHolofoil",
            ):
                cat_prices = prices.get(category, {})
                if cat_prices and cat_prices.get("market") is not None:
                    market_price = float(cat_prices["market"]) * rate
                    break

        return {
            "clean_name": card.get("name", "Unknown"),
            "high_res_image": card.get("images", {}).get("large"),
            "market_price": market_price,
            "tcgplayer_id": tcgplayer.get("productId"),
            "official_set_name": card.get("set", {}).get("name", ""),
            "official_set_number": card.get("number", ""),
        }

    def fetch_card_data(
        self,
        set_name: str,
        sequence_number: str,
        ocr_name: str | None = None,
        card_name: str | None = None,
    ) -> dict | None:
        set_name = self.resolver.resolve_set_name(set_name)
        clean_number = self._sanitize_sequence_number(sequence_number)
        name_to_use = card_name or ocr_name
        is_pokemon_generic = set_name.lower() == "pokemon" if set_name else False

        set_name_lower = set_name.lower() if set_name else ""
        is_promo_set = any(
            term in set_name_lower
            for term in ("promo", "first partner", "mega evolution")
        )

        # Promos-first: name + number before set matching
        if is_promo_set and name_to_use and name_to_use != "Unknown":
            query = f'name:"{name_to_use}" number:"{clean_number}"'
            cards = self._query_api(query, page_size=5)
            if cards:
                return self._extract_card_result(cards[0])

            words = [
                w
                for w in re.findall(r"\b\w+\b", name_to_use)
                if w.lower() not in {"the", "a", "an"}
            ]
            first_word = words[0] if words else name_to_use.split()[0]
            keywords = self._extract_set_keywords(set_name)
            set_kw = keywords[0] if keywords else None
            if set_kw:
                query_fallback = (
                    f'name:{first_word}* number:"{clean_number}" set.name:{set_kw}*'
                )
            else:
                query_fallback = f'name:{first_word}* number:"{clean_number}"'
            cards = self._query_api(query_fallback, page_size=10)
            if cards:
                best_card = cards[0]
                best_score = 0.0
                for card in cards:
                    api_name = card.get("name", "")
                    api_set = card.get("set", {}).get("name", "")
                    name_score = fuzz.WRatio(name_to_use.lower(), api_name.lower())
                    set_score = fuzz.WRatio(set_name.lower(), api_set.lower())
                    combined = name_score * 0.7 + set_score * 0.3
                    if combined > best_score:
                        best_score = combined
                        best_card = card
                return self._extract_card_result(best_card)

        # Manual refetch override (name search)
        if card_name:
            if is_pokemon_generic:
                query = f'name:"{card_name}" number:"{clean_number}"'
            else:
                query = (
                    f'name:"{card_name}" set.name:"{set_name}" number:"{clean_number}"'
                )
            cards = self._query_api(query, page_size=1)
            if cards:
                return self._extract_card_result(cards[0])

            query_fallback = f'name:"{card_name}" number:"{clean_number}"'
            cards = self._query_api(query_fallback, page_size=1)
            if cards:
                return self._extract_card_result(cards[0])

            words = [
                w
                for w in re.findall(r"\b\w+\b", card_name)
                if w.lower() not in {"the", "a", "an"}
            ]
            first_word = words[0] if words else card_name.split()[0]
            query_fuzzy = f'name:{first_word}* number:"{clean_number}"'
            cards = self._query_api(query_fuzzy, page_size=5)
            if cards:
                return self._extract_card_result(cards[0])

        # Strategy 1: exact set.name + number
        if is_pokemon_generic:
            if name_to_use and name_to_use != "Unknown":
                query = f'name:"{name_to_use}" number:"{clean_number}"'
            else:
                query = f'number:"{clean_number}"'
        else:
            query = f'set.name:"{set_name}" number:"{clean_number}"'
        cards = self._query_api(query, page_size=1)
        if cards:
            return self._extract_card_result(cards[0])

        # Strategy 2: keyword fuzzy set search
        if not is_pokemon_generic:
            keywords = self._extract_set_keywords(set_name)
            for kw in keywords:
                query = f'set.name:{kw}* number:"{clean_number}"'
                cards = self._query_api(query, page_size=5)
                if cards:
                    best_card = cards[0]
                    best_score = 0.0
                    for card in cards:
                        api_set = card.get("set", {}).get("name", "")
                        score = fuzz.WRatio(set_name.lower(), api_set.lower())
                        if score > best_score:
                            best_score = score
                            best_card = card
                    return self._extract_card_result(best_card)

        # Strategy 3: number-only broad search filtered by OCR name
        if ocr_name and ocr_name != "Unknown":
            query = f'number:"{clean_number}" name:"{ocr_name.split()[0]}*"'
            cards = self._query_api(query, page_size=10)
            if cards:
                best_card = cards[0]
                best_score = 0.0
                for card in cards:
                    score = fuzz.WRatio(ocr_name.lower(), card.get("name", "").lower())
                    if score > best_score:
                        best_score = score
                        best_card = card
                if best_score > 60:
                    return self._extract_card_result(best_card)

        fallback = self.resolver.fallback_search(
            set_name, sequence_number, name_to_use
        )
        if fallback:
            return fallback
        return None
