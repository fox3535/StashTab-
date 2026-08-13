"""
api_client.py - Scan-to-Search API Client
==========================================
Queries the free Pokemon TCG API to fetch verified card data
(official name, high-res images) using OCR-extracted set name
and sequence number as search keys.

This replaces reliance on raw OCR text for card identification,
eliminating hallucination issues and providing high-resolution
card artwork from the official database.

Search Strategy:
  1. Exact match on set.name + number
  2. Fuzzy fallback using set.name wildcard fragments + number
  3. Broad fallback using just the number (filtered by name similarity)
"""

import re
import requests
from rapidfuzz import fuzz


class SemanticResolver:
    """
    Maps user-provided or OCR set names to Pokemon TCG API official set names and
    implements recursive multi-pass query fallback searching.
    """
    PROMO_MAP = {
        'Mega Evolution Promos': 'Mega Evolution Black Star Promos',
        'Mega Evolutions Promo': 'Mega Evolution Black Star Promos',
        'First Partner Promos': 'First Partner Promos'
    }

    def __init__(self, api_client):
        self.api_client = api_client

    def resolve_set_name(self, set_name: str) -> str:
        """
        Check if the set_name exists in PROMO_MAP (case-insensitive).
        If it does, swap the user's string with the API's official string.
        """
        if not set_name:
            return set_name
        
        # Check for case-insensitive match
        for user_set, official_set in self.PROMO_MAP.items():
            if user_set.lower() == set_name.lower():
                return official_set
        return set_name

    def fallback_search(self, set_name: str, number: str, name: str, pass_num: int = 1) -> dict | None:
        """
        Multi-Pass recursive fallback search.
        
        Pass 1 (Official Name): Search using the resolved set name + number.
        Pass 2 (Broad Promo): If Pass 1 fails, search only using q=name:"{name}" (ignore set and number entirely).
        Pass 3 (Number Only): If Pass 2 fails, search q=name:"{name}" and filter the results locally in Python
                             to find the one where the number matches the OCR sequence number.
        """
        resolved_set = self.resolve_set_name(set_name)
        clean_number = self.api_client._sanitize_sequence_number(number)
        is_pokemon_generic = resolved_set.lower() == 'pokemon' if resolved_set else False

        if pass_num == 1:
            if is_pokemon_generic:
                if name and name != "Unknown":
                    query = f'name:"{name}" number:"{clean_number}"'
                else:
                    query = f'number:"{clean_number}"'
            else:
                query = f'set.name:"{resolved_set}" number:"{clean_number}"'
            print(f"[SemanticResolver] Pass 1 (Official Name): query='{query}'")
            cards = self.api_client._query_api(query, page_size=5)
            if cards:
                result = self.api_client._extract_card_result(cards[0])
                print(f"[SemanticResolver] Pass 1 succeeded: {result['clean_name']}")
                return result
            return self.fallback_search(set_name, number, name, pass_num=2)

        elif pass_num == 2:
            if not name or name == "Unknown":
                print("[SemanticResolver] Pass 2 skipped (no valid name).")
                return self.fallback_search(set_name, number, name, pass_num=3)
            
            query = f'name:"{name}"'
            print(f"[SemanticResolver] Pass 2 (Broad Promo): query='{query}'")
            cards = self.api_client._query_api(query, page_size=5)
            if cards:
                result = self.api_client._extract_card_result(cards[0])
                print(f"[SemanticResolver] Pass 2 succeeded: {result['clean_name']}")
                return result
            return self.fallback_search(set_name, number, name, pass_num=3)

        elif pass_num == 3:
            if not name or name == "Unknown":
                print("[SemanticResolver] Pass 3 skipped (no valid name).")
                return None
            
            query = f'name:"{name}"'
            print(f"[SemanticResolver] Pass 3 (Number Only): query='{query}'")
            cards = self.api_client._query_api(query, page_size=250)
            if cards:
                for card in cards:
                    card_num = card.get("number", "")
                    if self.api_client._sanitize_sequence_number(card_num) == clean_number:
                        result = self.api_client._extract_card_result(card)
                        print(f"[SemanticResolver] Pass 3 succeeded: {result['clean_name']}")
                        return result
            print("[SemanticResolver] All fallback passes failed.")
            return None

        return None


class PokemonAPI:
    """Client for the free Pokemon TCG API (https://api.pokemontcg.io/v2)."""

    BASE_URL = "https://api.pokemontcg.io/v2/cards"

    def __init__(self, api_key=None):
        """
        Initialize the API client.

        Args:
            api_key: Optional API key for higher rate limits.
                     The API works without a key (limited to 1000 req/day).
                     With a key, rate limits are significantly higher.
        """
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CardShopApp/1.0"})
        if api_key:
            self.session.headers.update({"X-Api-Key": api_key})
        self.resolver = SemanticResolver(self)

    def _sanitize_sequence_number(self, sequence_number: str) -> str:
        """
        Strips leading zeros, set prefixes, and denominator from a sequence number.

        Examples:
            '066/064'  -> '66'
            '199/165'  -> '199'
            'SWSH184'  -> '184'
            'SM210'    -> '210'
            '001/025'  -> '1'
            'POGO 030' -> '30'
            '148/142'  -> '148'
        """
        raw = sequence_number.strip().replace('O', '0').replace('o', '0')

        # Strip any text prefix (e.g., 'SWSH', 'SM', 'POGO ')
        # Find the first digit sequence in the string
        digits_match = re.search(r'(\d+)', raw)
        if not digits_match:
            return raw  # No digits found, return as-is

        # Take only the numerator (before any slash)
        numerator = digits_match.group(1)

        # Strip leading zeros but keep at least one digit
        return numerator.lstrip('0') or '0'

    def _extract_set_keywords(self, set_name: str) -> list[str]:
        """
        Extracts meaningful search keywords from an OCR set name.
        Strips common prefixes, abbreviations, and noise.

        Examples:
            'SV: 151'          -> ['151']
            'Stellar Crown'    -> ['Stellar', 'Crown']
            'Sun & Moon Promo' -> ['Sun', 'Moon', 'Promo']
            'POGO'             -> ['POGO']
        """
        # Remove punctuation except ampersand
        cleaned = re.sub(r'[:\'"!@#$%^*(){}[\]|\\<>~`]', ' ', set_name)
        # Split on whitespace and ampersand
        tokens = re.split(r'[\s&]+', cleaned)
        # Filter out short noise tokens and common OCR artifacts
        noise = {'sv', 'swsh', 'sm', 'xy', 'bw', 'dp', 'ex', 'the', 'of', 'and', 'a', ''}
        keywords = [t for t in tokens if t.lower() not in noise and len(t) > 1]
        # If nothing survived, try the original tokens
        if not keywords:
            keywords = [t for t in tokens if t.strip()]
        return keywords

    def _query_api(self, query: str, page_size: int = 5) -> list[dict]:
        """Executes a single API query with exponential backoff and returns the card list."""
        import time
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.session.get(
                    self.BASE_URL,
                    params={"q": query, "pageSize": page_size},
                    timeout=5
                )
                response.raise_for_status()
                return response.json().get("data", [])
            except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                if attempt < max_attempts - 1:
                    sleep_time = 1 if attempt == 0 else 2
                    print(f"[API] Attempt {attempt + 1} failed/timed out ({e}). Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    print(f"[API] All {max_attempts} attempts failed. Last error: {e}")
                    return []
            except Exception as e:
                print(f"[API] Unexpected error: {e}")
                return []
        return []

    def _extract_card_result(self, card: dict) -> dict:
        """Extracts the standardized result dictionary from an API card object."""
        market_price = None
        tcgplayer = card.get("tcgplayer", {})
        prices = tcgplayer.get("prices", {})
        if prices:
            for category in ["normal", "holofoil", "reverseHolofoil", "unlimitedHolofoil", "1stEditionHolofoil"]:
                cat_prices = prices.get(category, {})
                if cat_prices and "market" in cat_prices:
                    val = cat_prices.get("market")
                    if val is not None:
                        try:
                            import config
                            rate = getattr(config, 'USD_TO_CAD_RATE', 1.0)
                        except ImportError:
                            rate = 1.0
                        market_price = float(val) * rate
                        break
                        
        return {
            "clean_name": card.get("name", "Unknown"),
            "high_res_image": card.get("images", {}).get("large"),
            "market_price": market_price,
            "tcgplayer_id": tcgplayer.get("productId"),
            "official_set_name": card.get("set", {}).get("name", ""),
            "official_set_number": card.get("number", ""),
        }

    def fetch_card_data(self, set_name: str, sequence_number: str, ocr_name: str = None, card_name: str = None) -> dict | None:
        """
        Fetches verified card data from the Pokemon TCG API.

        Uses a multi-tier search strategy:
          1. Exact set.name + number match
          2. Keyword-based fuzzy set.name search + number
          3. Number-only broad search (filtered by OCR name similarity if provided)

        Args:
            set_name:        The set name as extracted by OCR (e.g., 'Stellar Crown', 'Sun & Moon Promo').
            sequence_number: The card number as extracted by OCR (e.g., '199/165', 'SM210', '066/064').
            ocr_name:        Optional OCR-extracted card name for disambiguation in broad searches.
            card_name:       Optional user-provided card name override for manual resync queries.

        Returns:
            A dictionary containing:
                - clean_name:     The official API card name.
                - high_res_image: The images.large URL for the high-res card image.
            Returns None if no match is found or a network error occurs.
        """
        # Pre-Query Translation
        set_name = self.resolver.resolve_set_name(set_name)
        clean_number = self._sanitize_sequence_number(sequence_number)
        name_to_use = card_name or ocr_name
        is_pokemon_generic = set_name.lower() == 'pokemon' if set_name else False

        # --- Local Database Fast-Track ---
        try:
            import sqlite3
            import os
            base_dir = os.path.dirname(os.path.dirname(__file__))
            db_path = os.path.join(base_dir, "image_db_manager", "card_images.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT local_path, card_name FROM Images
                    WHERE set_name = ? AND card_number = ? AND local_path IS NOT NULL
                ''', (set_name, clean_number))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    local_path = row['local_path']
                    if local_path and not os.path.isabs(local_path):
                        local_path = os.path.join(base_dir, local_path)
                        
                    if local_path and os.path.exists(local_path):
                        return {
                            "clean_name": row['card_name'] or "Unknown",
                            "high_res_image": local_path, # Local file path
                        "market_price": None,
                        "tcgplayer_id": None,
                        "official_set_name": set_name,
                        "official_set_number": sequence_number,
                    }
        except Exception as e:
            print(f"[API] Error checking local db: {e}")
            
        # ─── Promos-First Search Strategy ──────────────────────────────────
        set_name_lower = set_name.lower() if set_name else ""
        is_promo_set = any(term in set_name_lower for term in ['promo', 'first partner', 'mega evolution'])

        if is_promo_set and name_to_use and name_to_use != "Unknown":
            # Pass 1: Name + Number (Ignore set name entirely)
            query = f'name:"{name_to_use}" number:"{clean_number}"'
            print(f"[API] Promos-First initial query: {query}")
            cards = self._query_api(query, page_size=5)
            if cards:
                result = self._extract_card_result(cards[0])
                print(f"[API] Found (Promos-First initial): {result['clean_name']}")
                return result

            # Pass 2: Fallback allowing partial match on the set name, keeping name/number as primary
            words = [w for w in re.findall(r'\b\w+\b', name_to_use) if w.lower() not in {'the', 'a', 'an'}]
            first_word = words[0] if words else name_to_use.split()[0]
            
            keywords = self._extract_set_keywords(set_name)
            set_kw = keywords[0] if keywords else None

            if set_kw:
                query_fallback = f'name:{first_word}* number:"{clean_number}" set.name:{set_kw}*'
            else:
                query_fallback = f'name:{first_word}* number:"{clean_number}"'

            print(f"[API] Promos-First fallback query: {query_fallback}")
            cards = self._query_api(query_fallback, page_size=10)
            if cards:
                # Rank results locally by name and set similarity to find the best match
                best_card = cards[0]
                best_score = 0
                for card in cards:
                    api_name = card.get("name", "")
                    api_set = card.get("set", {}).get("name", "")
                    name_score = fuzz.WRatio(name_to_use.lower(), api_name.lower())
                    set_score = fuzz.WRatio(set_name.lower(), api_set.lower())
                    combined_score = name_score * 0.7 + set_score * 0.3
                    if combined_score > best_score:
                        best_score = combined_score
                        best_card = card

                result = self._extract_card_result(best_card)
                print(f"[API] Found (Promos-First fallback): {result['clean_name']} (score={best_score:.0f}%)")
                return result

        # ─── Manual Refetch Override (Name Search) ────────────────────────
        if card_name:
            if is_pokemon_generic:
                query = f'name:"{card_name}" number:"{clean_number}"'
            else:
                query = f'name:"{card_name}" set.name:"{set_name}" number:"{clean_number}"'
            print(f"[API] Manual refetch full match query: {query}")
            cards = self._query_api(query, page_size=1)
            if cards:
                result = self._extract_card_result(cards[0])
                print(f"[API] Found (manual full match): {result['clean_name']}")
                return result
            
            # Query Strategy 2 (The Promo Fallback)
            query_fallback = f'name:"{card_name}" number:"{clean_number}"'
            print(f"[API] Manual refetch promo fallback query: {query_fallback}")
            cards = self._query_api(query_fallback, page_size=1)
            if cards:
                result = self._extract_card_result(cards[0])
                print(f"[API] Found (manual promo fallback): {result['clean_name']}")
                return result

            # Query Strategy 3 (Fuzzy Name Fallback)
            words = [w for w in re.findall(r'\b\w+\b', card_name) if w.lower() not in {'the', 'a', 'an'}]
            first_word = words[0] if words else card_name.split()[0]
            query_fuzzy = f'name:{first_word}* number:"{clean_number}"'
            print(f"[API] Manual refetch fuzzy fallback query: {query_fuzzy}")
            cards = self._query_api(query_fuzzy, page_size=5)
            if cards:
                result = self._extract_card_result(cards[0])
                print(f"[API] Found (manual fuzzy fallback): {result['clean_name']}")
                return result

        # ─── Strategy 1: Exact set.name match ─────────────────────────────
        if is_pokemon_generic:
            if name_to_use and name_to_use != "Unknown":
                query = f'name:"{name_to_use}" number:"{clean_number}"'
            else:
                query = f'number:"{clean_number}"'
        else:
            query = f'set.name:"{set_name}" number:"{clean_number}"'
        cards = self._query_api(query, page_size=1)
        if cards:
            result = self._extract_card_result(cards[0])
            print(f"[API] Found (exact): {result['clean_name']} (set='{set_name}', number='{clean_number}')")
            return result

        # ─── Strategy 2: Keyword-based fuzzy set search ───────────────────
        if not is_pokemon_generic:
            keywords = self._extract_set_keywords(set_name)
            if keywords:
                # Build a wildcard query with the most distinctive keyword
                for kw in keywords:
                    query = f'set.name:{kw}* number:"{clean_number}"'
                    cards = self._query_api(query, page_size=5)
                    if cards:
                        # If multiple results, prefer the one whose set name best matches OCR
                        best_card = cards[0]
                        best_score = 0
                        for card in cards:
                            api_set = card.get("set", {}).get("name", "")
                            score = fuzz.WRatio(set_name.lower(), api_set.lower())
                            if score > best_score:
                                best_score = score
                                best_card = card

                        result = self._extract_card_result(best_card)
                        api_set = best_card.get("set", {}).get("name", "")
                        print(f"[API] Found (fuzzy): {result['clean_name']} (api_set='{api_set}', keyword='{kw}')")
                        return result

        # ─── Strategy 3: Number-only broad search ─────────────────────────
        if ocr_name and ocr_name != "Unknown":
            query = f'number:"{clean_number}" name:"{ocr_name.split()[0]}*"'
            cards = self._query_api(query, page_size=10)
            if cards:
                # Rank by name similarity to OCR name
                best_card = cards[0]
                best_score = 0
                for card in cards:
                    score = fuzz.WRatio(ocr_name.lower(), card.get("name", "").lower())
                    if score > best_score:
                        best_score = score
                        best_card = card

                if best_score > 60:
                    result = self._extract_card_result(best_card)
                    print(f"[API] Found (broad): {result['clean_name']} (score={best_score:.0f}%)")
                    return result

        # Multi-Pass Query Fallback Search
        print(f"[API] Standard strategies returned zero results. Initiating SemanticResolver fallback search...")
        fallback_result = self.resolver.fallback_search(set_name, sequence_number, name_to_use)
        if fallback_result:
            return fallback_result

        print(f"[API] No results for: set='{set_name}', number='{clean_number}'")
        return None
