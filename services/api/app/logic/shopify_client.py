"""Shopify client — ported from Mimir services/shopify_client.py (SaaS subset)."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
import requests

from app.models import ShopifyCredentials

API_VERSION = "2026-04"


class ShopifyClient:
    # Partner shared title cache — class-level so fetch_all_variants fills once
    _shared_title_cache: dict[str, dict[str, Any]] | None = None

    def __init__(self, credentials: ShopifyCredentials) -> None:
        self.store_url = credentials.store_url.rstrip("/")
        if not self.store_url.startswith("http"):
            self.store_url = f"https://{self.store_url}"
        self.clean_url = (
            self.store_url.replace("https://", "").replace("http://", "").strip("/")
        )
        self.access_token = credentials.api_key_encrypted
        self.api_version = API_VERSION
        self.base_url = f"https://{self.clean_url}/admin/api/{self.api_version}"
        self._location_id: int | None = None
        self._sku_cache: dict[str, dict[str, Any]] | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    def _request_with_retry(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict | bool:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        max_retries = 5
        for attempt in range(max_retries):
            response = requests.request(
                method, url, headers=self._headers(), timeout=20, **kwargs
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                sleep_time = float(retry_after) + 0.5 if retry_after else 2.0 * (
                    attempt + 1
                )
                time.sleep(sleep_time)
                continue
            response.raise_for_status()
            if method.upper() == "DELETE":
                return response.status_code == 200
            return response.json()

        response = requests.request(
            method, url, headers=self._headers(), timeout=20, **kwargs
        )
        response.raise_for_status()
        if method.upper() == "DELETE":
            return response.status_code == 200
        return response.json()

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        result = self._request_with_retry("GET", endpoint, params=params)
        return result if isinstance(result, dict) else {}

    def _post(self, endpoint: str, data: dict) -> dict:
        result = self._request_with_retry("POST", endpoint, json=data)
        return result if isinstance(result, dict) else {}

    def _put(self, endpoint: str, data: dict) -> dict:
        result = self._request_with_retry("PUT", endpoint, json=data)
        return result if isinstance(result, dict) else {}

    def _execute_graphql(self, query: str) -> dict:
        url = f"{self.base_url}/graphql.json"
        resp = httpx.post(
            url,
            json={"query": query},
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def test_connection(self) -> tuple[bool, str]:
        try:
            data = self._get("shop.json")
            shop_name = data.get("shop", {}).get("name", "Shopify")
            return True, f"Connected to {shop_name}"
        except Exception as exc:
            return False, str(exc)

    def get_recent_unfulfilled_orders(self) -> dict:
        return self._get(
            "orders.json",
            params={"status": "open", "fulfillment_status": "unfulfilled", "limit": 50},
        )

    def _upload_product_image(
        self, product_id: int, img_url: str | None, variant_id: int | None = None
    ) -> None:
        if not img_url:
            return
        encoded_string: str | None = None
        if str(img_url).startswith("http"):
            try:
                dl_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = requests.get(img_url, headers=dl_headers, timeout=15)
                resp.raise_for_status()
                encoded_string = base64.b64encode(resp.content).decode("utf-8")
            except Exception:
                return
        if encoded_string:
            payload: dict[str, Any] = {"image": {"attachment": encoded_string}}
            if variant_id:
                payload["image"]["variant_ids"] = [variant_id]
            try:
                self._post(f"products/{product_id}/images.json", payload)
            except Exception:
                pass

    def fetch_all_variants(self) -> dict[str, dict[str, Any]]:
        variants_map: dict[str, dict[str, Any]] = {}
        ShopifyClient._shared_title_cache = {}
        url = f"{self.base_url}/products.json?limit=250&status=active,draft,archived"
        try:
            while url:
                response = requests.get(url, headers=self._headers(), timeout=20)
                response.raise_for_status()
                products = response.json().get("products", [])
                for prod in products:
                    prod_title = prod.get("title")
                    if (
                        prod_title
                        and ShopifyClient._shared_title_cache is not None
                        and prod_title not in ShopifyClient._shared_title_cache
                    ):
                        ShopifyClient._shared_title_cache[prod_title] = prod
                    for var in prod.get("variants", []):
                        sku = var.get("sku")
                        if not sku:
                            continue
                        variants_map[sku] = {
                            "id": var["id"],
                            "product_id": prod["id"],
                            "price": float(var.get("price", 0.0)),
                            "inventory_quantity": int(var.get("inventory_quantity", 0)),
                            "title": prod.get("title"),
                            "has_images": len(prod.get("images", [])) > 0,
                        }
                link_header = response.headers.get("Link")
                url = None
                if link_header:
                    for link in link_header.split(","):
                        if 'rel="next"' in link:
                            start = link.find("<")
                            end = link.find(">")
                            if start != -1 and end != -1:
                                url = link[start + 1 : end]
                            break
            self._sku_cache = variants_map
            return variants_map
        except Exception:
            return {}

    def _get_cached_sku(self, sku: str) -> dict[str, Any] | None:
        if self._sku_cache is None:
            self._sku_cache = self.fetch_all_variants()
        return self._sku_cache.get(sku)

    def _get_cached_title(self, title: str) -> dict[str, Any] | None:
        if ShopifyClient._shared_title_cache is None:
            self._sku_cache = self.fetch_all_variants()
        cache = ShopifyClient._shared_title_cache or {}
        return cache.get(title)

    def create_or_update_product(self, item_data: dict[str, Any]) -> tuple[bool, str]:
        """Push or update a product on Shopify. Returns (success, message)."""
        try:
            result = self._create_or_update_product_inner(item_data)
            status = result.get("status", "")
            if status in ("updated_variant", "created_variant", "created_product"):
                return True, status
            return False, str(result)
        except Exception as exc:
            return False, str(exc)

    def _create_or_update_product_inner(self, item_data: dict[str, Any]) -> dict[str, Any]:
        card_name = item_data.get("name") or item_data.get("Name") or "Unknown Card"
        card_number = (
            item_data.get("sequence_number")
            or item_data.get("Number")
            or item_data.get("number")
            or ""
        )
        set_name = item_data.get("set_name") or item_data.get("Set") or "Unknown Set"
        is_sealed = item_data.get("card_type") == "Sealed"
        grade = item_data.get("grade") or ""
        condition = item_data.get("condition", "Near Mint")
        if not grade and condition:
            if any(
                str(condition).startswith(comp)
                for comp in ["PSA", "Beckett", "BGS", "CGC", "TAG", "SGC"]
            ):
                grade = condition

        game = item_data.get("game") or "Pokemon"
        variant = item_data.get("variant") or ""

        if is_sealed:
            product_type = "sealed"
            # Don't duplicate set if already present in the product name
            if set_name and set_name.lower() in card_name.lower():
                formatted_title = card_name
            else:
                formatted_title = f"{card_name} - {set_name}"
        elif grade and str(grade).strip():
            product_type = "graded"
            formatted_title = f"{card_name} - {card_number} - {set_name} - {grade}"
        else:
            product_type = "single"
            if str(game).lower() == "one piece":
                formatted_title = f"{card_name} - {card_number} - {variant} - {set_name}"
            else:
                formatted_title = f"{card_name} - {card_number} - {set_name}"

        formatted_title = formatted_title.replace(" -  - ", " - ")

        if is_sealed:
            condition = "None"
        elif product_type == "single":
            cond_map = {
                "None (Ungraded)": "NM (Near Mint)",
                "Near Mint": "NM (Near Mint)",
                "NM": "NM (Near Mint)",
                "NM (Near Mint)": "NM (Near Mint)",
                "Lightly Played": "LP (Lightly Played)",
                "LP": "LP (Lightly Played)",
                "LP (Lightly Played)": "LP (Lightly Played)",
                "Moderately Played": "MP (Moderately Played)",
                "MP": "MP (Moderately Played)",
                "MP (Moderately Played)": "MP (Moderately Played)",
                "Heavily Played": "HP (Heavily Played)",
                "HP": "HP (Heavily Played)",
                "HP (Heavily Played)": "HP (Heavily Played)",
                "Damaged": "DMG (Damaged)",
                "DMG": "DMG (Damaged)",
                "DMG (Damaged)": "DMG (Damaged)",
            }
            condition = cond_map.get(str(condition), "NM (Near Mint)")

        price = item_data.get("shop_listing_price") or item_data.get("market_price", 0.0)
        sku = item_data.get("sku", "")
        quantity = int(item_data.get("quantity", 1))
        img_url = item_data.get("custom_image_url") or item_data.get("image_url")

        target_product = None
        if sku:
            cached_var = self._get_cached_sku(sku)
            if cached_var:
                prod_response = self._get(f"products/{cached_var['product_id']}.json")
                if prod_response and "product" in prod_response:
                    target_product = prod_response["product"]

        if not target_product:
            cached_prod = self._get_cached_title(formatted_title)
            if cached_prod:
                target_product = cached_prod
            else:
                search_results = self._get(
                    "products.json", params={"title": formatted_title, "status": "any"}
                )
                for prod in search_results.get("products", []):
                    if prod.get("title") == formatted_title:
                        target_product = prod
                        break

        if target_product:
            variants = target_product.get("variants", [])
            existing_variant = None
            for var in variants:
                if var.get("title") == condition or var.get("option1") == condition:
                    existing_variant = var
                    break

            if existing_variant:
                var_id = existing_variant["id"]
                update_data = {
                    "variant": {
                        "id": var_id,
                        "price": str(price),
                        "sku": sku,
                        "inventory_quantity": quantity,
                    }
                }
                result = self._put(f"variants/{var_id}.json", update_data)
                if img_url and not target_product.get("images"):
                    self._upload_product_image(
                        target_product["id"], img_url, variant_id=var_id
                    )
                self.set_inventory(sku, quantity)
                return {"status": "updated_variant", "data": result}

            new_variant_data = {
                "variant": {
                    "product_id": target_product["id"],
                    "title": condition,
                    "option1": condition,
                    "price": str(price),
                    "sku": sku,
                    "inventory_management": "shopify",
                    "inventory_quantity": quantity,
                }
            }
            result = self._post(
                f"products/{target_product['id']}/variants.json", new_variant_data
            )
            if img_url and not target_product.get("images"):
                new_var_id = result.get("variant", {}).get("id")
                self._upload_product_image(
                    target_product["id"], img_url, variant_id=new_var_id
                )
            self.set_inventory(sku, quantity)
            return {"status": "created_variant", "data": result}

        new_product_data: dict[str, Any] = {
            "product": {
                "title": formatted_title,
                "product_type": product_type,
                "tags": f"AutoSync, {product_type}, {game}",
                "vendor": "StashTab",
                "status": "active",
                "published": True,
                "published_scope": "global",
                "variants": [
                    {
                        "title": condition,
                        "option1": condition,
                        "price": str(price),
                        "sku": sku,
                        "inventory_management": "shopify",
                        "inventory_quantity": quantity,
                    }
                ],
                "options": [{"name": "Condition", "values": [condition]}],
            }
        }
        if img_url and str(img_url).startswith("http"):
            try:
                resp = requests.get(img_url, timeout=15)
                resp.raise_for_status()
                encoded_string = base64.b64encode(resp.content).decode("utf-8")
                new_product_data["product"]["images"] = [{"attachment": encoded_string}]
            except Exception:
                pass

        result = self._post("products.json", new_product_data)
        if ShopifyClient._shared_title_cache is not None:
            new_prod = result.get("product", {})
            if new_prod:
                ShopifyClient._shared_title_cache[
                    new_prod.get("title", formatted_title)
                ] = new_prod
        if self._sku_cache is not None:
            new_prod = result.get("product", {})
            new_var = (new_prod.get("variants") or [{}])[0]
            if sku and new_var.get("id"):
                self._sku_cache[sku] = {
                    "id": new_var.get("id"),
                    "product_id": new_prod.get("id"),
                    "price": float(price),
                    "inventory_quantity": quantity,
                    "title": new_prod.get("title", formatted_title),
                    "has_images": bool(img_url),
                }
        return {"status": "created_product", "data": result}

    def adjust_inventory(self, sku: str, adjustment_quantity: int) -> tuple[bool, str]:
        try:
            query = f"""
            {{
              productVariants(first: 1, query: "sku:'{sku}'") {{
                edges {{
                  node {{
                    inventoryItem {{
                      legacyResourceId
                      inventoryLevels(first: 1) {{
                        edges {{
                          node {{
                            location {{
                              legacyResourceId
                            }}
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            gql_res = self._execute_graphql(query)
            edges = gql_res.get("data", {}).get("productVariants", {}).get("edges", [])
            if not edges:
                return False, f"SKU {sku} not found on Shopify"

            inv_item = edges[0]["node"]["inventoryItem"]
            inventory_item_id = int(inv_item["legacyResourceId"])
            loc_edges = inv_item.get("inventoryLevels", {}).get("edges", [])
            if not loc_edges:
                return False, f"No location mapped for SKU {sku}"

            location_id = int(loc_edges[0]["node"]["location"]["legacyResourceId"])
            payload = {
                "location_id": location_id,
                "inventory_item_id": inventory_item_id,
                "available_adjustment": int(adjustment_quantity),
            }
            res = self._post("inventory_levels/adjust.json", payload)
            if "inventory_level" in res:
                return True, "OK"
            return False, str(res)
        except Exception as exc:
            return False, str(exc)

    def set_inventory(self, sku: str, quantity: int) -> bool:
        try:
            query = f"""
            {{
              productVariants(first: 1, query: "sku:'{sku}'") {{
                edges {{
                  node {{
                    inventoryItem {{
                      legacyResourceId
                      inventoryLevels(first: 1) {{
                        edges {{
                          node {{
                            location {{
                              legacyResourceId
                            }}
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            gql_res = self._execute_graphql(query)
            edges = gql_res.get("data", {}).get("productVariants", {}).get("edges", [])
            if not edges:
                return False

            inv_item = edges[0]["node"]["inventoryItem"]
            inventory_item_id = int(inv_item["legacyResourceId"])
            loc_edges = inv_item.get("inventoryLevels", {}).get("edges", [])
            if not loc_edges:
                return False

            location_id = int(loc_edges[0]["node"]["location"]["legacyResourceId"])
            payload = {
                "location_id": location_id,
                "inventory_item_id": inventory_item_id,
                "available": int(quantity),
            }
            res = self._post("inventory_levels/set.json", payload)
            return "inventory_level" in res
        except Exception:
            return False

    def update_product_price(self, sku: str, new_price: float) -> bool:
        try:
            query = f"""
            {{
              productVariants(first: 1, query: "sku:'{sku}'") {{
                edges {{
                  node {{
                    legacyResourceId
                  }}
                }}
              }}
            }}
            """
            gql_res = self._execute_graphql(query)
            edges = gql_res.get("data", {}).get("productVariants", {}).get("edges", [])
            if not edges:
                return False

            variant_id = edges[0]["node"]["legacyResourceId"]
            payload = {
                "variant": {
                    "id": variant_id,
                    "price": f"{float(new_price):.2f}",
                }
            }
            res = self._put(f"variants/{variant_id}.json", payload)
            return "variant" in res
        except Exception:
            return False
