import os
import requests

# Fallback explicit loading of .env in case python-dotenv isn't installed or misses the cwd
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

class ShopifyClient:
    _shared_sku_cache = None
    _shared_title_cache = None
    
    def __init__(self):
        # Manual fallback parsing just in case
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, val = line.split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = val

        self.api_key = os.getenv("SHOPIFY_API_KEY")
        self.store_url = os.getenv("SHOPIFY_STORE_URL")
        self.api_version = "2026-04"
        
        if not self.api_key or not self.store_url:
            raise ValueError(f"Shopify API credentials missing from environment variables. Searched at: {env_path}")
            
        # Clean store URL in case it includes protocol
        self.clean_url = self.store_url.replace("https://", "").replace("http://", "").strip("/")
        
        self.base_url = f"https://{self.clean_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.api_key,
            "Content-Type": "application/json"
        }

    def _request_with_retry(self, method, endpoint, **kwargs):
        import time
        url = f"{self.base_url}/{endpoint}"
        max_retries = 5
        for attempt in range(max_retries):
            response = requests.request(method, url, headers=self.headers, **kwargs)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    sleep_time = float(retry_after) + 0.5
                else:
                    sleep_time = 2.0 * (attempt + 1)
                print(f"Rate limited by Shopify (429). Sleeping for {sleep_time} seconds before retry {attempt + 1}/{max_retries}...")
                time.sleep(sleep_time)
                continue
            response.raise_for_status()
            if method.upper() == "DELETE":
                return response.status_code == 200
            return response.json()
        
        # Fallback if max retries exceeded
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        if method.upper() == "DELETE":
            return response.status_code == 200
        return response.json()

    def _get(self, endpoint, params=None):
        return self._request_with_retry("GET", endpoint, params=params)

    def _post(self, endpoint, data):
        return self._request_with_retry("POST", endpoint, json=data)

    def _put(self, endpoint, data):
        return self._request_with_retry("PUT", endpoint, json=data)

    def _delete(self, endpoint):
        return self._request_with_retry("DELETE", endpoint)

    def _upload_product_image(self, product_id, img_url, variant_id=None):
        import os, base64, requests
        encoded_string = None
        if str(img_url).startswith("http"):
            try:
                dl_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(img_url, headers=dl_headers, timeout=10)
                resp.raise_for_status()
                encoded_string = base64.b64encode(resp.content).decode("utf-8")
            except Exception as e:
                print(f"Failed to download image from URL for existing product: {e}")
        else:
            clean_path = str(img_url).lstrip("\\/")
            if os.path.isfile(clean_path):
                with open(clean_path, "rb") as f:
                    encoded_string = base64.b64encode(f.read()).decode("utf-8")
            elif os.path.isfile(img_url):
                with open(img_url, "rb") as f:
                    encoded_string = base64.b64encode(f.read()).decode("utf-8")
                    
        if encoded_string:
            payload = {"image": {"attachment": encoded_string}}
            if variant_id:
                payload["image"]["variant_ids"] = [variant_id]
            try:
                self._post(f"products/{product_id}/images.json", payload)
                print(f"Successfully uploaded image for product {product_id}")
            except Exception as e:
                print(f"Failed to upload image to Shopify: {e}")

    def _get_cached_sku(self, sku):
        if ShopifyClient._shared_sku_cache is None:
            # Only cache variants if needed
            ShopifyClient._shared_sku_cache = self.fetch_all_variants()
        return ShopifyClient._shared_sku_cache.get(sku)

    def _get_cached_title(self, title):
        if ShopifyClient._shared_title_cache is None:
            # Ensure caches are built
            ShopifyClient._shared_sku_cache = self.fetch_all_variants()
        return ShopifyClient._shared_title_cache.get(title)

    def create_or_update_product(self, item_data):
        """
        Pushes a card to Shopify. Handles Variant logic.
        """
        # 1. Extract base fields safely
        card_name = item_data.get('Name') or item_data.get('name') or 'Unknown Card'
        card_number = item_data.get('Number') or item_data.get('number') or item_data.get('card_number') or item_data.get('sequence_number') or ''
        set_name = item_data.get('Set') or item_data.get('set_name') or 'Unknown Set'

        # 2. Extract condition/category flags
        is_sealed = item_data.get('Is_Sealed') or item_data.get('is_sealed') or (item_data.get('card_type') == 'Sealed') # Assuming boolean
        grade = item_data.get('Grade') or item_data.get('grade') # Assuming string, e.g., 'PSA 10'
        condition = item_data.get("condition", "Near Mint")
        
        # If grade wasn't passed explicitly, deduce it from condition string
        if not grade and condition:
            if any(condition.startswith(comp) for comp in ["PSA", "Beckett", "BGS", "CGC", "TAG", "SGC"]):
                grade = condition

        # 3. Apply Routing and Title formatting logic
        game = item_data.get('game') or 'Pokemon'
        variant = item_data.get('variant') or ''
        
        if is_sealed:
            product_type = "sealed"
            formatted_title = card_name
        elif grade and str(grade).strip() != "":
            product_type = "graded"
            # Graded title requires the grade at the end
            formatted_title = f"{card_name} - {card_number} - {set_name} - {grade}"
        else:
            product_type = "single"
            if game.lower() == "one piece":
                formatted_title = f"{card_name} - {card_number} - {variant} - {set_name}"
            else:
                formatted_title = f"{card_name} - {card_number} - {set_name}"

        # Clean up any double dashes if card_number is missing
        formatted_title = formatted_title.replace(" -  - ", " - ")
        condition = item_data.get("condition", "Near Mint")
        
        # Map condition strings to Shopify's expected formats
        if is_sealed:
            condition = "None"
        elif product_type == "single":
            if condition in ["None (Ungraded)", "Near Mint", "NM", "NM (Near Mint)"]:
                condition = "NM (Near Mint)"
            elif condition in ["Lightly Played", "LP", "LP (Lightly Played)"]:
                condition = "LP (Lightly Played)"
            elif condition in ["Moderately Played", "MP", "MP (Moderately Played)"]:
                condition = "MP (Moderately Played)"
            elif condition in ["Heavily Played", "HP", "HP (Heavily Played)"]:
                condition = "HP (Heavily Played)"
            elif condition in ["Damaged", "DMG", "DMG (Damaged)"]:
                condition = "DMG (Damaged)"
        # Use shop listing price if available, otherwise fallback to market price
        price = item_data.get("shop_listing_price", item_data.get("market_price", 0.0))
        sku = item_data.get("sku", "")
        quantity = int(item_data.get("quantity", 1))
        img_url = item_data.get("custom_image_url") or item_data.get("image_url")
        
        target_product = None
        
        # 0. Check if SKU already exists via our cache
        if sku:
            cached_var = self._get_cached_sku(sku)
            if cached_var:
                prod_id = cached_var['product_id']
                # Fetch full product to get variants and images
                prod_response = self._get(f"products/{prod_id}.json")
                if prod_response and "product" in prod_response:
                    target_product = prod_response["product"]
        
        # 1. Fallback: Check if the Master Product already exists by title
        if not target_product:
            cached_prod = self._get_cached_title(formatted_title)
            if cached_prod:
                target_product = cached_prod
            else:
                search_results = self._get("products.json", params={"title": formatted_title, "status": "any"})
                products = search_results.get("products", [])
                for prod in products:
                    if prod.get("title") == formatted_title:
                        target_product = prod
                        break
                
        if target_product:
            # 2. Check if a variant for this condition already exists
            variants = target_product.get("variants", [])
            existing_variant = None
            for var in variants:
                if var.get("title") == condition or var.get("option1") == condition:
                    existing_variant = var
                    break
                    
            if existing_variant:
                # Update existing variant (e.g., price and SKU)
                var_id = existing_variant["id"]
                update_data = {
                    "variant": {
                        "id": var_id,
                        "price": str(price),
                        "sku": sku,
                        "inventory_quantity": quantity
                    }
                }
                result = self._put(f"variants/{var_id}.json", update_data)
                
                # Check if we should upload the image
                if img_url:
                    if not target_product.get("images"):
                        self._upload_product_image(target_product["id"], img_url, variant_id=var_id)
                
                # Force update stock via inventory API to handle Shopify's deprecation of inventory_quantity
                self.set_inventory(sku, quantity)
                    
                return {"status": "updated_variant", "data": result}
            else:
                # Create a new variant for this condition
                new_variant_data = {
                    "variant": {
                        "product_id": target_product["id"],
                        "title": condition,
                        "option1": condition,
                        "price": str(price),
                        "sku": sku,
                        "inventory_management": "shopify",
                        "inventory_quantity": quantity
                    }
                }
                result = self._post(f"products/{target_product['id']}/variants.json", new_variant_data)
                
                # Check if we should upload the image
                has_images = len(target_product.get("images", [])) > 0
                if img_url and not has_images:
                    new_var_id = result.get("variant", {}).get("id")
                    self._upload_product_image(target_product["id"], img_url, variant_id=new_var_id)
                
                # Force update stock via inventory API to handle Shopify's deprecation of inventory_quantity
                self.set_inventory(sku, quantity)
                    
                if ShopifyClient._shared_sku_cache is not None:
                    ShopifyClient._shared_sku_cache[sku] = {
                        'id': new_var_id,
                        'product_id': target_product["id"],
                        'price': float(price),
                        'inventory_quantity': quantity,
                        'title': target_product.get("title", formatted_title),
                        'has_images': has_images or bool(img_url)
                    }

                return {"status": "created_variant", "data": result}
        else:
            # 3. Create entirely new product with this condition as the first variant
            new_product_data = {
                "product": {
                    "title": formatted_title,
                    "product_type": product_type,
                    "tags": f"AutoSync, {product_type}, {game}",
                    "vendor": "Card Shop App",
                    "status": "active", # Default to active so it's published live immediately
                    "published": True,
                    "published_scope": "global",
                    "variants": [
                        {
                            "title": condition,
                            "option1": condition,
                            "price": str(price),
                            "sku": sku,
                            "inventory_management": "shopify",
                            "inventory_quantity": quantity
                        }
                    ],
                    "options": [
                        {
                            "name": "Condition",
                            "values": [condition]
                        }
                    ]
                }
            }
            if img_url:
                import os, base64, requests
                if str(img_url).startswith("http"):
                    try:
                        resp = requests.get(img_url, timeout=10)
                        resp.raise_for_status()
                        encoded_string = base64.b64encode(resp.content).decode("utf-8")
                        new_product_data["product"]["images"] = [{"attachment": encoded_string}]
                    except Exception as e:
                        print(f"Failed to download image from URL: {e}")
                else:
                    # Handle case where path might have a leading slash
                    clean_path = str(img_url).lstrip("\\/")
                    if os.path.isfile(clean_path):
                        with open(clean_path, "rb") as f:
                            encoded_string = base64.b64encode(f.read()).decode("utf-8")
                        new_product_data["product"]["images"] = [{"attachment": encoded_string}]
                    elif os.path.isfile(img_url):
                        with open(img_url, "rb") as f:
                            encoded_string = base64.b64encode(f.read()).decode("utf-8")
                        new_product_data["product"]["images"] = [{"attachment": encoded_string}]
                
            result = self._post("products.json", new_product_data)
            
            if ShopifyClient._shared_sku_cache is not None:
                new_prod = result.get('product', {})
                new_var = new_prod.get('variants', [{}])[0]
                ShopifyClient._shared_sku_cache[sku] = {
                    'id': new_var.get('id'),
                    'product_id': new_prod.get('id'),
                    'price': float(price),
                    'inventory_quantity': quantity,
                    'title': new_prod.get('title', formatted_title),
                    'has_images': bool(img_url)
                }
            
            if ShopifyClient._shared_title_cache is not None:
                new_prod = result.get('product', {})
                if new_prod:
                    ShopifyClient._shared_title_cache[new_prod.get('title', formatted_title)] = new_prod

            return {"status": "created_product", "data": result}

    def get_recent_unfulfilled_orders(self):
        """
        Pulls new web orders down to sync with local physical inventory.
        """
        params = {
            "status": "open",
            "fulfillment_status": "unfulfilled"
        }
        return self._get("orders.json", params=params)

    def fetch_all_active_skus(self):
        """
        Fetches all variant SKUs currently active on Shopify via GraphQL pagination.
        Returns a dictionary of {sku: inventoryQuantity}.
        """
        active_skus = {}
        has_next_page = True
        cursor = None
        
        while has_next_page:
            cursor_param = f', after: "{cursor}"' if cursor else ""
            query = f"""
            {{
              productVariants(first: 250{cursor_param}) {{
                pageInfo {{
                  hasNextPage
                  endCursor
                }}
                edges {{
                  node {{
                    sku
                    inventoryQuantity
                  }}
                }}
              }}
            }}
            """
            try:
                res = self._execute_graphql(query)
                data = res.get('data', {}).get('productVariants', {})
                edges = data.get('edges', [])
                
                for edge in edges:
                    node = edge.get('node', {})
                    sku = node.get('sku')
                    qty = node.get('inventoryQuantity', 0)
                    if sku:
                        active_skus[sku] = qty
                        
                page_info = data.get('pageInfo', {})
                has_next_page = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')
            except Exception as e:
                print(f"Error fetching active SKUs from Shopify: {e}")
                break
                
        return active_skus

    def _execute_graphql(self, query):
        url = f"https://{self.clean_url}/admin/api/{self.api_version}/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self.api_key,
            "Content-Type": "application/json"
        }
        resp = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _get_primary_location_id(self):
        if not hasattr(self, '_location_id'):
            locs = self._get("locations.json")
            if locs and "locations" in locs and len(locs["locations"]) > 0:
                self._location_id = locs["locations"][0]["id"]
            else:
                self._location_id = None
        return self._location_id

    def adjust_inventory(self, sku, adjustment_quantity):
        """
        Adjusts Shopify inventory offline-first sync. Uses GraphQL to lookup inventory_item_id and location_id by SKU,
        then uses REST to adjust.
        """
        try:
            # Fetch inventory_item_id and its location_id via GraphQL
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
            edges = gql_res.get('data', {}).get('productVariants', {}).get('edges', [])
            if not edges:
                print(f"SKU {sku} not found on Shopify.")
                return False
                
            inv_item = edges[0]['node']['inventoryItem']
            inventory_item_id = int(inv_item['legacyResourceId'])
            
            loc_edges = inv_item.get('inventoryLevels', {}).get('edges', [])
            if not loc_edges:
                print(f"No location mapped for SKU {sku}.")
                return False
                
            location_id = int(loc_edges[0]['node']['location']['legacyResourceId'])

            # Adjust inventory using REST
            payload = {
                "location_id": location_id,
                "inventory_item_id": inventory_item_id,
                "available_adjustment": int(adjustment_quantity)
            }
            res = self._post("inventory_levels/adjust.json", payload)
            if "inventory_level" in res:
                return True
            return False
        except Exception as e:
            print(f"Failed to adjust inventory for SKU {sku}: {e}")
            return False

    def set_inventory(self, sku, quantity):
        """
        Sets absolute Shopify inventory offline-first sync. Uses GraphQL to lookup inventory_item_id and location_id by SKU,
        then uses REST to set.
        """
        try:
            # Fetch inventory_item_id and its location_id via GraphQL
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
            edges = gql_res.get('data', {}).get('productVariants', {}).get('edges', [])
            if not edges:
                print(f"SKU {sku} not found on Shopify.")
                return False
                
            inv_item = edges[0]['node']['inventoryItem']
            inventory_item_id = int(inv_item['legacyResourceId'])
            
            loc_edges = inv_item.get('inventoryLevels', {}).get('edges', [])
            if not loc_edges:
                print(f"No location mapped for SKU {sku}.")
                return False
                
            location_id = int(loc_edges[0]['node']['location']['legacyResourceId'])

            # Adjust inventory using REST
            payload = {
                "location_id": location_id,
                "inventory_item_id": inventory_item_id,
                "available": int(quantity)
            }
            res = self._post("inventory_levels/set.json", payload)
            if "inventory_level" in res:
                return True
            return False
        except Exception as e:
            print(f"Failed to set inventory for SKU {sku}: {e}")
            return False

    def update_product_price(self, sku, new_price):
        """
        Updates the price of a variant via Shopify REST API. Uses GraphQL to lookup legacyResourceId by SKU.
        """
        try:
            # 1. Fetch variant_id via GraphQL
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
            edges = gql_res.get('data', {}).get('productVariants', {}).get('edges', [])
            if not edges:
                print(f"SKU {sku} not found on Shopify for price update.")
                return False
                
            variant_id = edges[0]['node']['legacyResourceId']

            # 2. Update price using REST
            payload = {
                "variant": {
                    "id": variant_id,
                    "price": f"{float(new_price):.2f}"
                }
            }
            res = self._put(f"variants/{variant_id}.json", payload)
            if "variant" in res:
                return True
            return False
        except Exception as e:
            print(f"Failed to update price for SKU {sku}: {e}")
            return False


    def fetch_all_variants(self):
        """
        Fetches all variants across the entire Shopify catalog using cursor pagination.
        Returns a dict mapping SKU -> { 'id': variant_id, 'price': float, 'inventory_quantity': int, 'product_id': product_id }
        """
        from database import db_session, SystemSettings
        settings = db_session.query(SystemSettings).first()
        is_sim_mode = settings.sim_mode if settings else False

        if not self.store_url or not self.api_key:
            if not is_sim_mode:
                return {}
        
        if is_sim_mode:
            return {} # Can't fetch from a simulated store
            
        variants_map = {}
        ShopifyClient._shared_title_cache = {}
        url = f"{self.base_url}/products.json?limit=250&status=active,draft,archived"
        
        try:
            while url:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                
                products = response.json().get('products', [])
                for prod in products:
                    prod_title = prod.get('title')
                    if prod_title and prod_title not in ShopifyClient._shared_title_cache:
                        ShopifyClient._shared_title_cache[prod_title] = prod
                        
                    for var in prod.get('variants', []):
                        sku = var.get('sku')
                        if not sku:
                            continue
                        
                        price = float(var.get('price', 0.0))
                        qty = int(var.get('inventory_quantity', 0))
                        
                        variants_map[sku] = {
                            'id': var['id'],
                            'product_id': prod['id'],
                            'price': price,
                            'inventory_quantity': qty,
                            'title': prod.get('title'),
                            'has_images': len(prod.get('images', [])) > 0
                        }
                
                # Check for pagination Link header
                link_header = response.headers.get('Link')
                url = None
                if link_header:
                    links = link_header.split(',')
                    for link in links:
                        if 'rel="next"' in link:
                            # Extract the URL between < and >
                            start = link.find('<')
                            end = link.find('>')
                            if start != -1 and end != -1:
                                url = link[start+1:end]
                            break
                            
            return variants_map
        except Exception as e:
            print(f"Error fetching Shopify catalog: {e}")
            return {}
