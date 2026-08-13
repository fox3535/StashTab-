from database import db_session, InventoryItem, StagingItem
from services.shopify_client import ShopifyClient
import io
import re

print("[*] Starting bulk REVERSION of sequence numbers...")

c = ShopifyClient()

# 1. Parse out.txt
reversions = {} # map SKU -> (old_seq, new_seq)

try:
    with io.open('out.txt', encoding='utf-16le') as f:
        lines = f.readlines()
except FileNotFoundError:
    print("[!] out.txt not found. Cannot revert.")
    exit(1)

# Regex to match: "  [DB] Updating InventoryItem 454 (SKU: CS-8821): 171/165 -> 171"
# or "  [DB] Updating StagingItem 1 (SKU: CS-B2C7): 228/217 -> 228"
db_pattern = re.compile(r'\[DB\] Updating (?:InventoryItem|StagingItem) \d+ \(SKU: (CS-[A-Z0-9]+)\): (.*?) -> (.*)$')

for line in lines:
    match = db_pattern.search(line)
    if match:
        sku = match.group(1)
        old_seq = match.group(2).strip()
        new_seq = match.group(3).strip()
        reversions[sku] = (old_seq, new_seq)

print(f"[*] Found {len(reversions)} exact SKU reversions in out.txt to process.")

# 2. Update Local Database
inventory_count = 0
staging_count = 0

for sku, (old_seq, new_seq) in reversions.items():
    inv_item = db_session.query(InventoryItem).filter_by(sku=sku).first()
    if inv_item:
        print(f"  [DB] Reverting InventoryItem (SKU: {sku}): {inv_item.sequence_number} -> {old_seq}")
        inv_item.sequence_number = old_seq
        inventory_count += 1
        
    stg_item = db_session.query(StagingItem).filter_by(sku=sku).first()
    if stg_item:
        print(f"  [DB] Reverting StagingItem (SKU: {sku}): {stg_item.sequence_number} -> {old_seq}")
        stg_item.sequence_number = old_seq
        staging_count += 1

print(f"[*] Reverted {inventory_count} InventoryItems and {staging_count} StagingItems in local database.")

# 3. Update Shopify Listings
if reversions:
    print("\n[*] Fetching Shopify product mapping to update titles...")
    variants_map = c.fetch_all_variants()
    
    products_to_update = {} # product_id -> (old_seq, new_seq)
    
    for sku, (old_seq, new_seq) in reversions.items():
        var_data = variants_map.get(sku)
        if var_data:
            prod_id = var_data['product_id']
            products_to_update[prod_id] = (old_seq, new_seq)
        else:
            print(f"  [Shopify] SKU {sku} not found on Shopify. Skipping title reversion.")

    print(f"\n[*] Reverting {len(products_to_update)} unique products on Shopify...")
    
    for prod_id, (old_seq, new_seq) in products_to_update.items():
        resp = c._get(f"products/{prod_id}.json")
        if not resp or "product" not in resp:
            print(f"  [!] Could not fetch product {prod_id} from Shopify.")
            continue
            
        prod = resp["product"]
        current_title = prod.get("title", "")
        
        # Split title by ' - ' and replace the new_seq back with old_seq
        parts = [p.strip() for p in current_title.split(' - ')]
        updated_parts = []
        changed = False
        
        for part in parts:
            if part == new_seq:
                updated_parts.append(old_seq)
                changed = True
            else:
                updated_parts.append(part)
                
        if changed:
            reverted_title = ' - '.join(updated_parts)
            print(f"  [Shopify] Reverting Product {prod_id}: '{current_title}' -> '{reverted_title}'")
            
            payload = {
                "product": {
                    "id": prod_id,
                    "title": reverted_title
                }
            }
            update_resp = c._put(f"products/{prod_id}.json", payload)
            if not update_resp or "product" not in update_resp:
                print(f"    [!] Failed to update Shopify product {prod_id}.")
        else:
            print(f"  [Shopify] Product {prod_id} title '{current_title}' did not contain the sequence '{new_seq}'. Skipping.")

# Finally commit the database changes
try:
    db_session.commit()
    print("\n[*] Successfully committed all reversion changes to the local database.")
except Exception as e:
    db_session.rollback()
    print(f"\n[!] Error committing to database: {e}")

print("[*] Bulk REVERSION complete.")
