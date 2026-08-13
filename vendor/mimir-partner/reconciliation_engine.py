import os
import argparse
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import re
from rapidfuzz import fuzz
from database import db_session, Sale, InventoryItem, SystemSettings

def process_reconciliation(csv_path: str, since_date: str = None):
    print(f"[*] Starting Collectr Reconciliation Engine...")
    print(f"[*] Loading CSV from: {csv_path}")

    FAILURE = {"success": False, "removal_list": {}, "missing_from_collectr": {}, "unknown_cards": [], "prices_updated": 0, "updated_items_log": []}

    if not os.path.exists(csv_path):
        print(f"[!] Error: CSV file not found at {csv_path}")
        return FAILURE

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[!] Error parsing CSV: {e}")
        return FAILURE

    required_cols = ['Product Name', 'Set', 'Card Number']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"[!] Error: Missing required columns in CSV: {missing_cols}")
        return FAILURE

    cutoff_date = None
    if since_date:
        try:
            cutoff_date = datetime.strptime(since_date, "%Y-%m-%d")
            print(f"[*] Filtering sales on or after: {cutoff_date.date()}")
        except ValueError:
            pass
    else:
        # Default to 7 days for sales checking if not specified to prevent ancient sales from triggering removals
        cutoff_date = datetime.now() - timedelta(days=7)
        print(f"[*] Filtering sales on or after: {cutoff_date.date()} (Default 7-day window)")

    db_session.expire_all()
    settings = db_session.query(SystemSettings).first()

    # Fetch ALL inventory items (including stock=0, so we can match them)
    all_inventory = db_session.query(InventoryItem).all()
    
    # Pre-process inventory for matching
    inv_lookup = []
    for inv_item in all_inventory:
        inv_lookup.append({
            'id': inv_item.id,
            'sku': inv_item.sku,
            'orig_name': inv_item.name,
            'orig_num': inv_item.sequence_number,
            'orig_set': inv_item.set_name,
            'stock': inv_item.stock,
            'name': str(inv_item.name).strip().lower(),
            'set_name': str(inv_item.set_name).strip().lower() if inv_item.set_name else "",
            'sequence_number': str(inv_item.sequence_number).strip().lower() if inv_item.sequence_number else "",
            'price': float(inv_item.price) if inv_item.price is not None else 0.0,
            'condition': inv_item.condition or 'NM',
            'variant': inv_item.variant or 'Normal',
            'card_type': inv_item.card_type or 'Single',
            'obj': inv_item
        })

    price_col = None
    c_lower_map = {col.lower().strip(): col for col in df.columns}
    for p in ['market price', 'market value', 'current value', 'value', 'price', 'unit price']:
        if p in c_lower_map:
            price_col = c_lower_map[p]
            break
    if not price_col:
        for p in ['market', 'value', 'price']:
            for c_lower, col in c_lower_map.items():
                if p in c_lower and 'total' not in c_lower:
                    price_col = col
                    break
            if price_col: break
            
    cond_col = c_lower_map.get('condition', c_lower_map.get('card condition', c_lower_map.get('state')))
    var_col = c_lower_map.get('variance', c_lower_map.get('variant', c_lower_map.get('finish')))
    qty_col = c_lower_map.get('quantity', c_lower_map.get('qty', c_lower_map.get('count')))
    graded_col = c_lower_map.get('grade', c_lower_map.get('graded'))
    bgs_col = c_lower_map.get('bgs', c_lower_map.get('bgs grade'))

    def norm_seq(seq):
        if pd.isna(seq) or not seq: return ""
        s = str(seq).strip().lower()
        # Split on '/' or '-' and take the first part to handle '119/189' matching '119'
        s = re.split(r'[/\\-]', s)[0]
        return re.sub(r'[^a-z0-9]', '', s)

    def is_seq_match(seq1, seq2):
        if not seq1 or not seq2: return True
        return seq1 == seq2

    # 1. Aggregate CSV rows
    csv_aggregated = []
    for index, row in df.iterrows():
        csv_price = 0.0
        if price_col and pd.notna(row.get(price_col)):
            try:
                raw_val = str(row[price_col]).replace(',', '')
                num_match = re.search(r'\d+\.?\d*', raw_val)
                if num_match: csv_price = float(num_match.group())
            except Exception: pass
                
        if csv_price <= 0.0: continue

        csv_name = str(row['Product Name']).strip().lower() if pd.notna(row['Product Name']) else ""
        csv_set = str(row['Set']).strip().lower() if pd.notna(row['Set']) else ""
        csv_num = norm_seq(row['Card Number'])
        
        raw_cond = str(row[cond_col]).strip() if cond_col and pd.notna(row.get(cond_col)) else 'Near Mint'
        raw_cond_lower = raw_cond.lower()
        is_graded = False
        cond_code = 'NM'
        
        if graded_col and pd.notna(row.get(graded_col)):
            g_val = str(row[graded_col]).strip()
            if g_val and g_val.lower() not in ['nan', 'none', 'null', 'false', 'no', '', 'ungraded']:
                is_graded = True
                if g_val.lower() not in ['yes', 'true', 'graded']: cond_code = g_val
                else:
                    if bgs_col and pd.notna(row.get(bgs_col)):
                        b_val = str(row[bgs_col]).strip()
                        if b_val and b_val.lower() not in ['nan', 'none', 'null', '']: cond_code = f"BGS {b_val}"
                        else: cond_code = raw_cond
                    else: cond_code = raw_cond

        if not is_graded and any(term in raw_cond_lower for term in ['psa', 'bgs', 'cgc', 'grade', 'gem', 'pristine']):
            is_graded = True
            cond_code = raw_cond

        if not is_graded:
            if 'lightly' in raw_cond_lower or raw_cond_lower == 'lp': cond_code = 'LP'
            elif 'moderately' in raw_cond_lower or raw_cond_lower == 'mp': cond_code = 'MP'
            elif 'heavily' in raw_cond_lower or raw_cond_lower == 'hp': cond_code = 'HP'
            elif 'damaged' in raw_cond_lower or raw_cond_lower == 'dmg': cond_code = 'DMG'

        raw_variant = str(row[var_col]).strip() if var_col and pd.notna(row.get(var_col)) else 'Normal'
        csv_qty = 1
        if qty_col and pd.notna(row.get(qty_col)):
            try: csv_qty = int(row[qty_col])
            except: pass

        card_num = str(row['Card Number']).strip() if pd.notna(row['Card Number']) else ""
        if str(card_num).lower() == 'nan': card_num = ""

        card_type = "Graded" if is_graded else ("Sealed" if card_num == "" else "Single")

        csv_aggregated.append({
            'orig_name': str(row['Product Name']).strip() if pd.notna(row['Product Name']) else "Unknown",
            'orig_set': str(row['Set']).strip() if pd.notna(row['Set']) else "",
            'orig_num': card_num,
            'name': csv_name,
            'set_name': csv_set,
            'sequence_number': csv_num,
            'price': csv_price,
            'condition': cond_code,
            'variant': raw_variant,
            'quantity': csv_qty,
            'card_type': card_type,
            'is_graded': is_graded
        })

    # Combine quantities for duplicate rows in CSV
    combined_csv = {}
    for row in csv_aggregated:
        key = (row['name'], row['set_name'], row['sequence_number'])
        if key not in combined_csv:
            combined_csv[key] = row.copy()
        else:
            combined_csv[key]['quantity'] += row['quantity']
            combined_csv[key]['is_graded'] = combined_csv[key]['is_graded'] or row['is_graded']

    # Aggregate DB inventory by name, set_name, sequence_number
    inv_aggregated = {}
    for inv in inv_lookup:
        key = (inv['name'], inv['set_name'], norm_seq(inv['orig_num']))
        if key not in inv_aggregated:
            inv_aggregated[key] = {
                'orig_name': inv['orig_name'],
                'orig_set': inv['orig_set'],
                'orig_num': inv['orig_num'],
                'stock': 0,
                'skus': [],
                'price': inv['price'],
                'card_type': inv['card_type'],
                'items': []
            }
        inv_aggregated[key]['stock'] += inv['stock']
        inv_aggregated[key]['skus'].append(inv['sku'])
        inv_aggregated[key]['items'].append(inv)
        
    removal_list = defaultdict(list)
    unknown_cards = []
    missing_from_collectr = defaultdict(list)
    updated_items_log = []
    prices_updated = 0
    matched_inv_keys = set()

    for key, row in combined_csv.items():
        # Match against aggregated inventory
        matched_inv = None
        matched_key = None
        for inv_key, inv_data in inv_aggregated.items():
            if inv_key in matched_inv_keys: continue
            
            seq_match = is_seq_match(inv_key[2], row['sequence_number'])
            set_match = fuzz.partial_ratio(inv_key[1], row['set_name']) >= 70 if inv_key[1] and row['set_name'] else True
            name_match = (inv_key[0] == row['name'])
            
            if seq_match and set_match and name_match:
                matched_inv = inv_data
                matched_key = inv_key
                matched_inv_keys.add(inv_key)
                break
                
        if matched_inv:
            inv_stock = matched_inv['stock']
            csv_qty = row['quantity']
            
            # Update Price if necessary
            if not (settings and settings.omit_graded_from_recon and row['is_graded']):
                try:
                    for inv in matched_inv['items']:
                        inv_price = inv['price']
                        price_diff = abs(inv_price - row['price'])
                        if price_diff >= 0.01:
                            from logic import calculate_shop_listing_price
                            shop_price = calculate_shop_listing_price(row['price'], inv['card_type'])
                            log_msg = f"  -> Price Update for {inv['sku']} ({inv['orig_name']} {inv['orig_num']}):  ->  (shop: )"
                            print(log_msg)
                            updated_items_log.append(log_msg)
                            inv['obj'].old_price = inv_price
                            inv['obj'].price = row['price']
                            inv['obj'].shop_listing_price = shop_price
                            inv['obj'].needs_update = True
                            prices_updated += 1
                except Exception as e:
                    print(f"[!] Error processing price for {row['name']}: {e}")

            if csv_qty > inv_stock:
                # Excess in Collectr. Was it sold recently?
                extra_qty = csv_qty - inv_stock
                recent_sales = 0
                if cutoff_date:
                    sales = db_session.query(Sale).filter(Sale.sku.in_(matched_inv['skus']), Sale.is_reconciled==False).filter(Sale.timestamp >= cutoff_date).all()
                    recent_sales = len(sales)
                    
                qty_to_remove = min(recent_sales, extra_qty)
                unaccounted = extra_qty - qty_to_remove

                if qty_to_remove > 0:
                    display_set = matched_inv['orig_set'] if matched_inv['orig_set'] else "Unknown Set"
                    removal_list[display_set].append({
                        'name': matched_inv['orig_name'],
                        'num': matched_inv['orig_num'] if matched_inv['orig_num'] else "??",
                        'sku': matched_inv['skus'][0],
                        'skus': matched_inv['skus'],
                        'price': matched_inv['price'],
                        'qty_to_remove': qty_to_remove
                    })
                
                if unaccounted > 0:
                    # Add to staging so they can process it.
                    unknown_cards.append({
                        'name': matched_inv['orig_name'],
                        'set_name': matched_inv['orig_set'],
                        'card_number': matched_inv['orig_num'],
                        'price': row['price'],
                        'condition': row['condition'],
                        'variant': row['variant'],
                        'quantity': unaccounted,
                        'card_type': row['card_type'],
                        'sku': matched_inv['skus'][0] # Pass first SKU so staging merges it!
                    })
            elif inv_stock > csv_qty:
                # Excess in POS. Needs to be added to Collectr.
                missing_qty = inv_stock - csv_qty
                display_set = matched_inv['orig_set'] if matched_inv['orig_set'] else "Unknown Set"
                missing_from_collectr[display_set].append({
                    'name': matched_inv['orig_name'],
                    'num': matched_inv['orig_num'] if matched_inv['orig_num'] else "??",
                    'sku': matched_inv['skus'][0],
                    'missing_qty': missing_qty
                })
        else:
            # Completely unknown card (not in DB at all)
            unknown_cards.append({
                'name': row['orig_name'],
                'set_name': row['orig_set'],
                'card_number': row['orig_num'],
                'price': row['price'],
                'condition': row['condition'],
                'variant': row['variant'],
                'quantity': row['quantity'],
                'card_type': row['card_type']
            })

    # Check for items in POS that weren't in Collectr at all (stock > 0)
    for inv_key, inv_data in inv_aggregated.items():
        if inv_key not in matched_inv_keys and inv_data['stock'] > 0:
            display_set = inv_data['orig_set'] if inv_data['orig_set'] else "Unknown Set"
            missing_from_collectr[display_set].append({
                'name': inv_data['orig_name'],
                'num': inv_data['orig_num'] if inv_data['orig_num'] else "??",
                'sku': inv_data['skus'][0],
                'missing_qty': inv_data['stock']
            })
    if prices_updated > 0:
        db_session.commit()
        print(f"[*] Committed {prices_updated} price updates to inventory.")

    matches_found = sum(len(v) for v in removal_list.values())
    
    # 3. Generate Output Report
    output_file = "removal_list.txt"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("========================================================\n")
            f.write("              COLLECTR REMOVAL LIST\n")
            f.write("========================================================\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if cutoff_date:
                f.write(f"Filter: Sales since {cutoff_date.date()}\n")
            f.write(f"\n=============================\n")
            f.write(f"PRICE UPDATES ({prices_updated})\n")
            f.write(f"=============================\n")
            if not updated_items_log:
                f.write("No prices differed from the Collectr CSV.\n")
            else:
                for log_str in updated_items_log:
                    f.write(log_str + "\n")

            f.write(f"\n========================================================\n")
            f.write(f"REMOVAL LIST (Matches Found: {matches_found})\n")
            f.write("========================================================\n\n")

            if matches_found == 0:
                f.write("No sold items were found in the Collectr CSV. Your portfolio is up to date!\n")
            else:
                f.write("Please remove the following items from your Collectr portfolio:\n\n")
                for set_name in sorted(removal_list.keys()):
                    f.write(f"[{set_name}]\n")
                    items = sorted(removal_list[set_name], key=lambda x: x['name'])
                    for item in items:
                        qty_rem = item.get('qty_to_remove', 1)
                        f.write(f"  - {item['name']} (#{item['num']}) [-{qty_rem}] [SKU: {item['sku']}]\n")
                    f.write("\n")
            
            f.write(f"\n========================================================\n")
            f.write(f"UNKNOWN CARDS (Not in DB: {len(unknown_cards)})\n")
            f.write("========================================================\n\n")
            if not unknown_cards:
                f.write("All Collectr cards matched local inventory.\n")
            else:
                f.write("The following Collectr cards were not found in the local DB and have been sent to Staging:\n\n")
                for c in unknown_cards:
                    f.write(f"  - {c['name']} (#{c['card_number']}) [{c['set_name']}] ${c['price']:.2f} (Qty: {c['quantity']})\n")
                    
        print(f"[*] Success! Found {matches_found} items to remove, {len(unknown_cards)} unknown cards, and {sum(len(v) for v in missing_from_collectr.values())} missing from Collectr.")
        print(f"[*] Report generated and saved to: {os.path.abspath(output_file)}")
        
    except Exception as e:
        print(f"[!] Error writing output file: {e}")

    return {
        "success": True,
        "removal_list": dict(removal_list),
        "missing_from_collectr": dict(missing_from_collectr),
        "unknown_cards": unknown_cards,
        "prices_updated": prices_updated,
        "updated_items_log": updated_items_log,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile local sales against Collectr CSV.")
    parser.add_argument("csv_file", help="Path to the Collectr export.csv file")
    parser.add_argument("--since", help="Optional cutoff date for sales in YYYY-MM-DD format", default=None)
    args = parser.parse_args()
    process_reconciliation(args.csv_file, args.since)
