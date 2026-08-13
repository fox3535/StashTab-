from database import db_session, InventoryItem, StagingItem
from api_client import PokemonAPI
from services.shopify_client import ShopifyClient
import requests
import re

print("[*] Starting bulk sanitization of sequence numbers...")

api = PokemonAPI()
c = ShopifyClient()

# 1. Update Local Database
inventory_items_to_update = db_session.query(InventoryItem).filter(InventoryItem.sequence_number.like('%/%')).all()
staging_items_to_update = db_session.query(StagingItem).filter(StagingItem.sequence_number.like('%/%')).all()

print(f"[*] Found {len(inventory_items_to_update)} InventoryItems and {len(staging_items_to_update)} StagingItems to sanitize.")

# We will track which SKUs were modified so we can update them on Shopify
modified_skus = {} # map SKU -> (old_seq, new_seq)

for item in inventory_items_to_update:
    old_seq = item.sequence_number
    new_seq = api._sanitize_sequence_number(old_seq)
    
    # Store for Shopify update
    modified_skus[item.sku] = (old_seq, new_seq)
    
    print(f"  [DB] Updating InventoryItem {item.id} (SKU: {item.sku}): {old_seq} -> {new_seq}")
    item.sequence_number = new_seq

for item in staging_items_to_update:
    old_seq = item.sequence_number
    new_seq = api._sanitize_sequence_number(old_seq)
    print(f"  [DB] Updating StagingItem {item.id} (SKU: {item.sku}): {old_seq} -> {new_seq}")
    item.sequence_number = new_seq

# 2. Update Shopify Listings
if modified_skus:
    print("\n[*] Fetching Shopify product mapping to update titles...")
    variants_map = c.fetch_all_variants()
    
    # Group by product_id so we only update each product once
    products_to_update = {} # product_id -> (old_seq, new_seq)
    
    for sku, (old_seq, new_seq) in modified_skus.items():
        var_data = variants_map.get(sku)
        if var_data:
            prod_id = var_data['product_id']
            # We assume a single product's variants all share the same old_seq/new_seq pair
            # since they represent the same card in different conditions.
            products_to_update[prod_id] = (old_seq, new_seq)
        else:
            print(f"  [Shopify] SKU {sku} not found on Shopify. Skipping title update.")

    print(f"\n[*] Updating {len(products_to_update)} unique products on Shopify...")
    
    for prod_id, (old_seq, new_seq) in products_to_update.items():
        # Fetch current product details to get its exact title
        resp = c._get(f"products/{prod_id}.json")
        if not resp or "product" not in resp:
            print(f"  [!] Could not fetch product {prod_id} from Shopify.")
            continue
            
        prod = resp["product"]
        old_title = prod.get("title", "")
        
        # Replace the exact sequence number in the title
        # The title format is typically "Name - Number - Set" or "Name - Number - Variant - Set"
        # We replace the sequence number specifically bounded by spaces/dashes to avoid partial matches
        
        # Safe replacement: only replace the old sequence number if it's sandwiched between dashes
        # e.g., " - 167/159 - " -> " - 167 - "
        # Also handle if it's right before graded text: " - 167/159 - PSA 9"
        
        # Split title by ' - ' and replace the part that matches exactly
        parts = [p.strip() for p in old_title.split(' - ')]
        updated_parts = []
        changed = False
        
        for part in parts:
            if part == old_seq:
                updated_parts.append(new_seq)
                changed = True
            else:
                updated_parts.append(part)
                
        if changed:
            new_title = ' - '.join(updated_parts)
            print(f"  [Shopify] Updating Product {prod_id}: '{old_title}' -> '{new_title}'")
            
            payload = {
                "product": {
                    "id": prod_id,
                    "title": new_title
                }
            }
            update_resp = c._put(f"products/{prod_id}.json", payload)
            if not update_resp or "product" not in update_resp:
                print(f"    [!] Failed to update Shopify product {prod_id}.")
        else:
            print(f"  [Shopify] Product {prod_id} title '{old_title}' did not contain the exact sequence '{old_seq}'. Skipping.")

# Finally commit the database changes
try:
    db_session.commit()
    print("\n[*] Successfully committed all changes to the local database.")
except Exception as e:
    db_session.rollback()
    print(f"\n[!] Error committing to database: {e}")

print("[*] Bulk sanitization complete.")
