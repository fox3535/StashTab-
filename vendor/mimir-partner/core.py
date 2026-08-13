import os
import cv2
import time
import traceback
from rapidfuzz import fuzz
import requests
from PIL import Image
from dataclasses import dataclass
from typing import Any, Optional, Protocol
from config import USE_API_PRICE, DEBUG_MODE

@dataclass
class Result:
    success: bool
    data: Any = None
    error_message: Optional[str] = None

class IDatabaseClient(Protocol):
    def add_to_staging(self, card_data: dict) -> Result:
        ...

class IOCRClient(Protocol):
    def parse_row_data(self, image: Any) -> Result:
        ...

class IAPIClient(Protocol):
    def fetch_card_data(self, set_name: str, seq_num: str, ocr_name: str, local_name: str, thumb_path: str) -> Result:
        ...

class SQLAlchemyDatabaseClient(IDatabaseClient):
    def add_to_staging(self, card_data: dict) -> Result:
        try:
            # We defer the import to avoid circular dependency loops if logic imports core
            from logic import add_item_to_staging
            add_item_to_staging(card_data)
            return Result(success=True)
        except Exception as e:
            return Result(success=False, error_message=f"DB Error: {str(e)}")

class EasyOCRClient(IOCRClient):
    def parse_row_data(self, image: Any) -> Result:
        try:
            from ocr_engine import RowParser
            parser = RowParser()
            parsed_data = parser.parse_row_data(image)
            if not parsed_data:
                return Result(success=False, error_message="OCR returned no data.")
            return Result(success=True, data=parsed_data)
        except Exception as e:
            return Result(success=False, error_message=f"OCR Error: {str(e)}")

class PokemonTCGAPIClient(IAPIClient):
    def __init__(self):
        from api_client import PokemonAPI
        self._api = PokemonAPI()

    def fetch_card_data(self, set_name: str, seq_num: str, ocr_name: str, local_name: str, thumb_path: str) -> Result:
        try:
            api_result = self._api.fetch_card_data(set_name, seq_num, ocr_name=ocr_name)
            if not api_result:
                return Result(success=False, error_message="API returned no result.")
                
            api_name = api_result.get("clean_name", "")
            name_score = fuzz.WRatio(local_name.lower(), api_name.lower())
            
            result_data = {"match_verified": False}
            
            if name_score >= 80:
                result_data["match_verified"] = True
                result_data["official_set_name"] = api_result.get("official_set_name", "")
                result_data["tcgplayer_id"] = api_result.get("tcgplayer_id")
                result_data["market_price"] = api_result.get("market_price")
                
                # API image gathering is deferred until Validate & Fetch Images is clicked in Settings
                pass
                        
            return Result(success=True, data=result_data)
        except Exception as e:
            return Result(success=False, error_message=f"API Error: {str(e)}")

class CoreManager:
    """
    Orchestrates the OCR parsing, API verification, and Database storage for a single card image.
    """
    def __init__(self, db_client: IDatabaseClient, ocr_client: Optional[IOCRClient], api_client: IAPIClient, start_poller: bool = True):
        self.db = db_client
        self.ocr = ocr_client  # May be None if OCR pipeline is disabled
        self.api = api_client
        
        if start_poller:
            import threading
            self.poller_thread = threading.Thread(target=self._background_polling_loop, daemon=True)
            self.poller_thread.start()

    def _pull_shopify_orders(self):
        from database import db_session, InventoryItem, Sale, OnlinePullQueue
        from services.shopify_client import ShopifyClient
        from logic import output_queue
        
        try:
            client = ShopifyClient()
            orders_data = client.get_recent_unfulfilled_orders()
            orders = orders_data.get('orders', [])
            
            new_pulls = 0
            for order in orders:
                order_id = str(order.get('id'))
                # Check if it already exists in OnlinePullQueue
                existing_order = db_session.query(OnlinePullQueue).filter_by(order_id=order_id).first()
                if existing_order:
                    continue
                    
                line_items = order.get('line_items', [])
                for item in line_items:
                    sku = item.get('sku')
                    if not sku: continue
                    quantity = int(item.get('quantity', 1))
                    price = float(item.get('price', 0.0))
                    
                    inv_item = db_session.query(InventoryItem).filter_by(sku=sku).first()
                    if inv_item:
                        # 1. Lower local database inventory
                        if inv_item.stock >= quantity:
                            inv_item.stock -= quantity
                        else:
                            inv_item.stock = 0
                            
                        # Auto-pause if available stock reaches 0
                        available_qty = inv_item.stock - (getattr(inv_item, 'paused_stock', 0) or 0)
                        if available_qty <= 0 and getattr(inv_item, 'sync_status', '') == 'active':
                            inv_item.sync_status = 'paused'
                            
                        # 2. Record sale history
                        cost = inv_item.cost if inv_item.cost else 0.0
                        profit = price - cost
                        sale = Sale(
                            item_name=inv_item.name,
                            sku=sku,
                            sold_price=price,
                            profit=profit,
                            transaction_type="Online Sale"
                        )
                        db_session.add(sale)
                        
                        # 3. Add to OnlinePullQueue for the "Sold Online" tab
                        pull_req = OnlinePullQueue(
                            order_id=order_id,
                            sku=sku,
                            status='pending_pull'
                        )
                        db_session.add(pull_req)
                        new_pulls += 1
                        
                        # 4. Trigger Toast Notification via queue
                        output_queue.put({
                            'type': 'online_sale',
                            'card_name': inv_item.name,
                            'set_name': inv_item.set_name,
                            'sequence_number': inv_item.sequence_number,
                            'condition': inv_item.condition
                        })
                        
            if new_pulls > 0:
                db_session.commit()
                
        except Exception as e:
            print(f"Error pulling Shopify orders: {e}")

    def _process_sync_outbox(self, progress_callback=None):
        from database import db_session, SyncOutbox, InventoryItem
        from services.shopify_client import ShopifyClient
        
        outbox_items = db_session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'pending').all()
        approved_items = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'approved').all()
        
        total_items = len(outbox_items) + len(approved_items)
        if total_items == 0:
            if progress_callback:
                progress_callback(0, 0, "No pending items to sync")
            return
            
        print(f"Processing {len(outbox_items)} outbox items and {len(approved_items)} approved items in Force Sync...")
        
        try:
            shopify = ShopifyClient()
        except Exception as e:
            print(f"Failed to initialize ShopifyClient: {e}")
            if progress_callback:
                progress_callback(0, total_items, f"Shopify Client Error: {e}")
            return
            
        current_index = 0
        if progress_callback:
            progress_callback(current_index, total_items, "Starting sync...")

        synced_product_skus = set()

        import time
        for item in outbox_items:
            current_index += 1
            if progress_callback:
                progress_callback(current_index, total_items, f"SKU: {item.sku} ({item.action_type})")
            
            time.sleep(0.5) # Rate limit to approx 2 requests per second
            
            if item.action_type == 'sale':
                try:
                    success, msg = shopify.adjust_inventoryLevel(item.sku, item.quantity_change)
                    if success:
                        print(f"Successfully synced inventory adjustment for SKU {item.sku}")
                        item.sync_status = 'synced'
                    else:
                        print(f"Failed to sync SKU {item.sku}: {msg}")
                except Exception as e:
                    print(f"Connection error syncing SKU {item.sku}: {e}. Keeping in outbox.")
            
            elif item.action_type in ('price_update', 'stock_update'):
                try:
                    inv_item = db_session.query(InventoryItem).filter_by(sku=item.sku).first()
                    if inv_item:
                        if item.sku in synced_product_skus:
                            print(f"SKU {item.sku} already full-synced in this batch. Marking as synced.")
                            item.sync_status = 'synced'
                            if inv_item.sync_status == 'approved':
                                inv_item.sync_status = 'active'
                            continue

                        from logic import calculate_shop_listing_price
                        item_data = {
                            "name": inv_item.name,
                            "sequence_number": inv_item.sequence_number,
                            "set_name": inv_item.set_name,
                            "condition": inv_item.condition,
                            "market_price": inv_item.price,
                            "shop_listing_price": item.new_price if (item.action_type == 'price_update' and item.new_price > 0) else (getattr(inv_item, 'shop_listing_price', None) or calculate_shop_listing_price(inv_item.price, inv_item.card_type)),
                            "sku": inv_item.sku,
                            "quantity": max(0, inv_item.stock - (getattr(inv_item, 'paused_stock', 0) or 0)) if inv_item.sync_status != 'paused' else 0,
                            "card_type": inv_item.card_type,
                            "variant": inv_item.variant,
                            "custom_image_url": getattr(inv_item, 'custom_image_url', None) or getattr(inv_item, 'image_url', None),
                            "game": getattr(inv_item, 'game', 'Pokemon')
                        }
                        success, msg = shopify.create_or_update_product(item_data)
                        if success:
                            print(f"Successfully synced {item.action_type} for SKU {item.sku}")
                            item.sync_status = 'synced'
                            synced_product_skus.add(item.sku)
                            if inv_item.sync_status == 'approved':
                                inv_item.sync_status = 'active'
                        else:
                            print(f"Failed full sync for SKU {item.sku}: {msg}")
                    else:
                        print(f"SKU {item.sku} not found in DB. Marking as synced to clear.")
                        item.sync_status = 'synced'
                except Exception as e:
                    print(f"Connection error syncing {item.action_type} for SKU {item.sku}: {e}. Keeping in outbox.")
                    
        for inv_item in approved_items:
            if inv_item.sync_status == 'active' or inv_item.sku in synced_product_skus:
                current_index += 1 # Was already updated above
                if progress_callback:
                    progress_callback(current_index, total_items, f"{inv_item.name} (Already synced)")
                continue # Already handled above by outbox loop
            current_index += 1
            if progress_callback:
                progress_callback(current_index, total_items, f"Approved: {inv_item.name}")
            
            time.sleep(0.5) # Rate limit to approx 2 requests per second
            
            try:
                from logic import calculate_shop_listing_price
                item_data = {
                    "name": inv_item.name,
                    "sequence_number": inv_item.sequence_number,
                    "set_name": inv_item.set_name,
                    "condition": inv_item.condition,
                    "market_price": inv_item.price,
                    "shop_listing_price": getattr(inv_item, 'shop_listing_price', None) or calculate_shop_listing_price(inv_item.price, inv_item.card_type),
                    "sku": inv_item.sku,
                    "quantity": max(0, inv_item.stock - (getattr(inv_item, 'paused_stock', 0) or 0)) if inv_item.sync_status != 'paused' else 0,
                    "card_type": inv_item.card_type,
                    "variant": inv_item.variant,
                    "custom_image_url": getattr(inv_item, 'custom_image_url', None) or getattr(inv_item, 'image_url', None),
                    "game": getattr(inv_item, 'game', 'Pokemon')
                }
                success, msg = shopify.create_or_update_product(item_data)
                if success:
                    print(f"Successfully force synced approved item SKU {inv_item.sku}")
                    inv_item.sync_status = 'active'
                    synced_product_skus.add(inv_item.sku)
                else:
                    print(f"Failed force sync for approved SKU {inv_item.sku}: {msg}")
            except Exception as e:
                print(f"Connection error force syncing SKU {inv_item.sku}: {e}")
                
        try:
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"Failed to commit SyncOutbox updates: {e}")

    def _background_polling_loop(self):
        while True:
            try:
                print('Poller waking up...')
                self._pull_shopify_orders()
                self._process_sync_outbox()
                print('Poller finished cycle. Sleeping for 60 seconds...')
            except Exception as e:
                print('ERROR IN POLLING THREAD:')
                print(traceback.format_exc())
            time.sleep(30)

    def process_card(self, row_image: Any, profile: dict) -> Result:
        try:
            # 1. OCR Parsing
            if self.ocr is None:
                return Result(success=False, error_message="OCR client not configured.")
            ocr_result = self.ocr.parse_row_data(row_image)
            if not ocr_result.success:
                return ocr_result
            
            parsed_data = ocr_result.data
            
            # Extract basic data needed
            h, w = row_image.shape[:2]
            sku = f"CS-{os.urandom(2).hex().upper()}"
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{sku}.png")
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            
            # Save OCR-cropped thumbnail as fallback
            art_bbox = parsed_data.get("art_bbox")
            if art_bbox:
                ax, ay, aw, ah = art_bbox
                thumb_slice = row_image[ay:ay+ah, ax:ax+aw]
            else:
                slices = profile.get('relative_slices', {})
                sx1, sy1, sx2, sy2 = slices.get('card_image', (0.00, 0.00, 0.20, 1.00))
                thumb_slice = row_image[int(h*sy1):int(h*sy2), int(w*sx1):int(w*sx2)]
                
            thumb_pil = Image.fromarray(cv2.cvtColor(thumb_slice, cv2.COLOR_BGR2RGB))
            thumb_pil.save(thumb_path)
            
            ocr_set = parsed_data.get("set_name", "Unknown")
            ocr_seq = parsed_data.get("sequence_number", "Unknown")
            ocr_name = parsed_data.get("name", "Unknown")
            set_conf = parsed_data.get("confidence_scores", {}).get("set_name", 100.0)
            
            set_is_unreliable = (ocr_set in ("Unknown", "Unknown Set") or set_conf < 50)
            api_set_to_use = "pokemon" if set_is_unreliable else ocr_set
            
            # 2. API Verification
            if ocr_seq != "Unknown" and ocr_seq != "000":
                api_result = self.api.fetch_card_data(api_set_to_use, ocr_seq, ocr_name, local_name=ocr_name, thumb_path=thumb_path)
                
                # Merge API results if successful
                if api_result.success and api_result.data:
                    api_data = api_result.data
                    if api_data.get("match_verified"):
                        official_set = api_data.get("official_set_name", "")
                        if official_set and (ocr_set in ("Unknown", "Unknown Set") or set_is_unreliable):
                            parsed_data["set_name"] = official_set
                        
                        api_tcgplayer_id = api_data.get("tcgplayer_id")
                        if api_tcgplayer_id:
                            parsed_data["tcgplayer_id"] = api_tcgplayer_id
                        
                        api_market_price = api_data.get("market_price")
                        if USE_API_PRICE and api_market_price is not None:
                            parsed_data["market_price"] = api_market_price
            
            name_conf = parsed_data["confidence_scores"]["name"]
            needs_review = name_conf < 70
            
            card_data = {
                "name": parsed_data["name"],
                "set_name": parsed_data["set_name"],
                "sequence_number": parsed_data["sequence_number"],
                "market_price": parsed_data["market_price"],
                "variant": parsed_data["variant"],
                "card_type": parsed_data["card_type"],
                "condition": parsed_data["condition"],
                "quantity": parsed_data["quantity"],
                "sku": sku,
                "image_path": thumb_path,
                "needs_review": needs_review,
                "confidence_scores": parsed_data["confidence_scores"]
            }
            if "tcgplayer_id" in parsed_data:
                card_data["tcgplayer_id"] = parsed_data["tcgplayer_id"]

            # Deduplication Check
            sig = f"{parsed_data.get('name', '')}_{parsed_data.get('set_name', '')}_{parsed_data.get('sequence_number', '')}_{parsed_data.get('variant', '')}_{parsed_data.get('condition', '')}".lower().strip()
            
            # To avoid importing scraped_signatures, we can let logic.py handle it, or we check it here
            from logic import scraped_signatures
            if sig in scraped_signatures:
                return Result(success=True, data=card_data) # Already saved
                
            scraped_signatures.add(sig)

            # 3. Save to Database Staging
            db_result = self.db.add_to_staging(card_data)
            if not db_result.success:
                return db_result
                
            return Result(success=True, data=card_data)
            
        except Exception as e:
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()
            return Result(success=False, error_message=f"CoreManager processing error: {str(e)}")

    def verify_shopify_consistency(self):
        """
        Scans all active items in the local DB and compares them to Shopify's live variants.
        If a mismatch is found (price or stock), queues a SyncOutbox task.
        """
        from database import db_session, InventoryItem, SyncOutbox
        from logic import calculate_shop_price
        
        print("[*] Starting Shopify Consistency Check...")
        
        # 1. Fetch Shopify Variants
        from services.shopify_client import ShopifyClient
        shop_client = ShopifyClient()
        shopify_variants = shop_client.fetch_all_variants()
        
        if not shopify_variants:
            return False, "Failed to fetch variants from Shopify. Check credentials or connection."
            
        print(f"[*] Fetched {len(shopify_variants)} variants from Shopify.")
        
        # 2. Fetch Active Local DB Items
        local_items = db_session.query(InventoryItem).all()
        
        mismatches_found = 0
        
        for item in local_items:
            target_stock = item.stock if item.sync_status != 'paused' else 0
            
            target_price = calculate_shop_price(item.price)
            if getattr(item, 'shop_listing_price', None) != target_price:
                item.shop_listing_price = target_price
                
            sku = item.sku
            
            if sku in shopify_variants:
                shop_var = shopify_variants[sku]
                shop_price = shop_var['price']
                shop_qty = shop_var['inventory_quantity']
                shop_has_images = shop_var.get('has_images', False)
                
                needs_price_update = abs(target_price - shop_price) > 0.01
                needs_stock_update = target_stock != shop_qty
                
                local_img = getattr(item, 'custom_image_url', None) or getattr(item, 'image_url', None)
                import os
                has_valid_img = local_img and (str(local_img).startswith('http') or os.path.exists(local_img))
                needs_image_update = has_valid_img and not shop_has_images
                
                if needs_price_update or needs_image_update:
                    reason = "Price mismatch" if needs_price_update else "Missing Image"
                    print(f"[*] {reason} detected for {sku}")
                    outbox = SyncOutbox(action_type='price_update', sku=sku, quantity_change=0, new_price=target_price)
                    db_session.add(outbox)
                    mismatches_found += 1
                    
                elif needs_stock_update:
                    print(f"[*] Stock mismatch for {sku}: DB={target_stock} vs Shopify={shop_qty}")
                    # stock_update action handles quantity pushing
                    outbox = SyncOutbox(action_type='stock_update', sku=sku, quantity_change=0, new_price=0.0)
                    db_session.add(outbox)
                    mismatches_found += 1
                    
        db_session.commit()
        return True, f"Consistency check complete. Queued {mismatches_found} fixes to Outbox."
