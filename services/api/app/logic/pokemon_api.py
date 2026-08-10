"""Pokemon TCG API client — ported from partner api_client.py."""

from __future__ import annotations

import re

import httpx
from rapidfuzz import fuzz

from app.config import settings


class PokemonAPI:
    BASE_URL = "https://api.pokemontcg.io/v2/cards"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "pokemon_tcg_api_key", "") or None
        self.headers = {"User-Agent": "StashTab/1.0"}
        if self.api_key:
            self.headers["X-Api-Key"] = self.api_key

    @staticmethod
    def _sanitize_sequence_number(sequence_number: str) -> str:
        raw = sequence_number.strip().replace("O", "0").replace("o", "0")
        match = re.search(r"(\d+)", raw)
        if not match:
            return raw
        return match.group(1).lstrip("0") or "0"

    def _query_api(self, query: str, page_size: int = 5) -> list[dict]:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    self.BASE_URL,
                    params={"q": query, "pageSize": page_size},
                    headers=self.headers,
                )
                resp.raise_for_status()
                return resp.json().get("data", [])
        except Exception:
            return []

    @staticmethod
    def _extract_card_result(card: dict) -> dict:
        market_price = None
        tcgplayer = card.get("tcgplayer", {})
        prices = tcgplayer.get("prices", {})
        for category in (
            "normal",
            "holofoil",
            "reverseHolofoil",
            "unlimitedHolofoil",
            "1stEditionHolofoil",
        ):
            cat_prices = prices.get(category, {})
            if cat_prices and cat_prices.get("market") is not None:
                market_price = float(cat_prices["market"])
                break

        return {
            "clean_name": card.get("name", "Unknown"),
            "high_res_image": card.get("images", {}).get("large"),
            "market_price": market_price,
            "official_set_name": card.get("set", {}).get("name", ""),
            "official_set_number": card.get("number", ""),
        }

    def fetch_card_data(
        self,
        set_name: str,
        sequence_number: str,
        card_name: str | None = None,
    ) -> dict | None:
        clean_number = self._sanitize_sequence_number(sequence_number)
        name = card_name or ""

        queries = []
        if name and set_name:
            queries.append(f'name:"{name}" set.name:"{set_name}" number:"{clean_number}"')
        if name:
            queries.append(f'name:"{name}" number:"{clean_number}"')
        if set_name:
            queries.append(f'set.name:"{set_name}" number:"{clean_number}"')
        queries.append(f'number:"{clean_number}"')

        for query in queries:
            cards = self._query_api(query, page_size=10)
            if not cards:
                continue
            if name:
                best = max(
                    cards,
                    key=lambda c: fuzz.WRatio(name.lower(), c.get("name", "").lower()),
                )
                return self._extract_card_result(best)
            return self._extract_card_result(cards[0])
        return None
