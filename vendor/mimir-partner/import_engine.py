import os
import pandas as pd
from database import db_session, InventoryItem, StagingItem
from api_client import PokemonAPI

def generate_sku():
    """Generates a random unique SKU in the format CS-XXXX."""
    return f"CS-{os.urandom(2).hex().upper()}"

def process_csv_import(file_path: str, refresh_callback=None, progress_callback=None):
    """
    Parses a CSV file, looks up cards via PokemonAPI, and inserts them into the inventory.
    """
    print(f"[*] Starting CSV import from: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        return False
        
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[!] Failed to parse CSV: {e}")
        return False

    df.columns = [str(c).strip() for c in df.columns]
    col_map = {str(c).lower(): str(c) for c in df.columns}
    
    name_col = col_map.get('product name', col_map.get('name'))
    set_col = col_map.get('set', col_map.get('set name'))
    num_col = col_map.get('card number', col_map.get('number'))
    
    if not name_col or not set_col:
        print("[!] Missing name or set columns.")
        return False

    game_col = col_map.get('game', col_map.get('category'))
    # Removed strict Pokemon filter so One Piece and Yu-Gi-Oh! can be imported

    cost_col = col_map.get('cost', col_map.get('price paid', col_map.get('total paid')))
    market_price_col = col_map.get('market price', col_map.get('market value', col_map.get('market_value', col_map.get('price', col_map.get('value')))))
    qty_col = col_map.get('quantity', col_map.get('qty'))
    
    # Fallbacks if exact match failed
    if not market_price_col:
        for c in col_map.keys():
            if 'price' in c or 'value' in c:
                market_price_col = col_map[c]
                break
    if not cost_col:
        for c in col_map.keys():
            if 'cost' in c or 'paid' in c:
                cost_col = col_map[c]
                break
    if not qty_col:
        for c in col_map.keys():
            if 'qty' in c or 'count' in c or 'quantity' in c:
                qty_col = col_map[c]
                break
                
    print(f"[*] Mapped Columns -> Name: {name_col}, Set: {set_col}, Price: {market_price_col}, Cost: {cost_col}, Qty: {qty_col}")

    api = PokemonAPI()
    success_count = 0
    review_count = 0
    sealed_count = 0
    error_count = 0
    
    total_rows = len(df)
    
    for index, row in df.iterrows():
        if progress_callback:
            progress_callback(index + 1, total_rows)
            
        try:
            raw_name = str(row[name_col]).strip() if name_col else "Unknown"
            raw_set = str(row[set_col]).strip() if set_col else "Unknown"
            raw_number = str(row[num_col]).strip() if num_col and str(row[num_col]).lower() != 'nan' else ""
            
            game = "Pokemon"
            if game_col:
                g_val = str(row[game_col]).strip()
                if g_val and g_val.lower() != 'nan':
                    game = g_val
                    
            if game.lower() == "one piece":
                if raw_number and "-" in raw_number:
                    prefix = raw_number.split("-")[0].strip()
                    if prefix and prefix not in raw_set:
                        raw_set = f"{raw_set} - {prefix}"
            
            variant = None
            var_col = col_map.get('variance', col_map.get('variant', col_map.get('rarity')))
            if var_col:
                var_val = str(row[var_col]).strip()
                if var_val and var_val.lower() != 'nan':
                    variant = var_val

            is_sealed = (raw_number == '' and not ((variant and 'don!!' in variant.lower()) or ('don!!' in raw_name.lower())))
            
            quantity = 1
            if qty_col:
                try:
                    quantity = int(row[qty_col])
                except (ValueError, TypeError):
                    quantity = 1
                    
            cost_paid = 0.00
            if cost_col:
                try:
                    cost_paid = float(str(row[cost_col]).replace('$', '').replace(',', ''))
                except (ValueError, TypeError):
                    cost_paid = 0.00
                    
            price = 0.00
            if market_price_col:
                try:
                    p_str = str(row[market_price_col]).strip()
                    if p_str.lower() not in ['nan', 'none', 'null', '', 'n/a', '-']:
                        price = float(p_str.replace('$', '').replace(',', '').replace(' ', ''))
                except (ValueError, TypeError):
                    price = 0.00
            
            condition = 'None (Ungraded)'
            is_graded = False
            
            cond_col = col_map.get('condition', col_map.get('card condition', col_map.get('state')))
            if cond_col:
                val = str(row[cond_col]).strip()
                if val and val.lower() not in ['nan', 'none', 'null', '']:
                    condition = val
                    
            graded_col = col_map.get('grade', col_map.get('graded'))
            if graded_col:
                g_val = str(row[graded_col]).strip()
                if g_val and g_val.lower() not in ['nan', 'none', 'null', 'false', 'no', '', 'ungraded']:
                    is_graded = True
                    if g_val.lower() not in ['yes', 'true', 'graded']:
                        condition = g_val
                    else:
                        bgs_col = col_map.get('bgs', col_map.get('bgs grade'))
                        if bgs_col:
                            b_val = str(row[bgs_col]).strip()
                            if b_val and b_val.lower() not in ['nan', 'none', 'null', '']:
                                condition = f"BGS {b_val}"
                                
            needs_review = False
            image_url = ""
            name = raw_name
            if is_sealed:
                card_type = "Sealed"
            elif is_graded:
                card_type = "Graded"
            else:
                card_type = "Single"
            
            if not is_sealed:
                # API image gathering is now deferred until the user explicitly clicks Validate & Fetch Images in Settings
                needs_review = True
                review_count += 1
            else:
                sealed_count += 1
                
            sku = generate_sku()
            
            # Duplicate detection: separate logic for sealed vs single
            if is_sealed:
                existing_item = db_session.query(InventoryItem).filter(
                    InventoryItem.name == name,
                    InventoryItem.set_name == raw_set,
                    InventoryItem.card_type == 'Sealed'
                ).first()
            else:
                existing_item = db_session.query(InventoryItem).filter(
                    InventoryItem.name == name,
                    InventoryItem.set_name == raw_set,
                    InventoryItem.sequence_number == raw_number,
                    InventoryItem.condition == condition,
                    InventoryItem.game == game
                ).first()


            if existing_item:
                existing_item.stock = quantity
                if cost_paid > 0:
                    existing_item.cost = round(cost_paid, 2)
                if price > 0:
                    existing_item.price = round(price, 2)
                if not existing_item.image_url and image_url:
                    existing_item.image_url = image_url
            else:
                while db_session.query(InventoryItem).filter_by(sku=sku).first() is not None or \
                      db_session.query(StagingItem).filter_by(sku=sku).first() is not None:
                    sku = generate_sku()
                    
                new_item = InventoryItem(
                    sku=sku,
                    name=name,
                    set_name=raw_set,
                    sequence_number=raw_number if not is_sealed else None,
                    cost=cost_paid,
                    price=price,
                    stock=quantity,
                    card_type=card_type,
                    condition=condition,
                    variant=variant,
                    needs_review=needs_review,
                    image_url=image_url,
                    sync_status='paused',
                    game=game
                )
                db_session.add(new_item)
                db_session.commit()
                
        except Exception as e:
            print(f"[!] Error processing row {index+1}: {e}")
            error_count += 1

    try:
        db_session.commit()
        print(f"[*] Import Complete!")
        print(f"    - Successfully matched singles: {success_count}")
        print(f"    - Sealed products added: {sealed_count}")
        print(f"    - Imported but needs review: {review_count}")
        print(f"    - Errors/Skipped: {error_count}")
        return True
    except Exception as e:
        db_session.rollback()
        print(f"[!] Database commit failed: {e}")
        return False

def patch_conditions_from_csv(file_path: str, progress_callback=None):
    """
    Parses a CSV file and updates the condition and card_type of existing inventory items
    that match the Product Name, Set, and Sequence Number.
    """
    print(f"[*] Starting Condition Patch from: {file_path}")
    if not os.path.exists(file_path):
        return 0, 0
        
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[!] Failed to parse CSV: {e}")
        return 0, 0

    df.columns = [str(c).strip() for c in df.columns]
    col_map = {str(c).lower(): str(c) for c in df.columns}
    
    name_col = col_map.get('product name', col_map.get('name'))
    set_col = col_map.get('set', col_map.get('set name'))
    num_col = col_map.get('card number', col_map.get('number'))
    game_col = col_map.get('game', col_map.get('category'))
    
    if not name_col or not set_col:
        print("[!] Missing name or set columns.")
        return 0, 0

    updated_count = 0
    not_found_count = 0
    total_rows = len(df)
    
    for index, row in df.iterrows():
        if progress_callback:
            progress_callback(index + 1, total_rows)
            
        try:
            raw_name = str(row[name_col]).strip() if name_col else "Unknown"
            raw_set = str(row[set_col]).strip() if set_col else "Unknown"
            raw_number = str(row[num_col]).strip() if num_col and str(row[num_col]).lower() != 'nan' else ""
            variant = None
            var_col = col_map.get('variance', col_map.get('variant', col_map.get('rarity')))
            if var_col:
                var_val = str(row[var_col]).strip()
                if var_val and var_val.lower() != 'nan':
                    variant = var_val

            is_sealed = (raw_number == '' and not ((variant and 'don!!' in variant.lower()) or ('don!!' in raw_name.lower())))
            
            game = "Pokemon"
            if game_col:
                g_val = str(row[game_col]).strip()
                if g_val and g_val.lower() != 'nan':
                    game = g_val
                    
            if game.lower() == "one piece":
                if raw_number and "-" in raw_number:
                    prefix = raw_number.split("-")[0].strip()
                    if prefix and prefix not in raw_set:
                        raw_set = f"{raw_set} - {prefix}"
            
            condition = 'None (Ungraded)'
            is_graded = False
            
            cond_col = col_map.get('condition', col_map.get('card condition', col_map.get('state')))
            if cond_col:
                val = str(row[cond_col]).strip()
                if val and val.lower() not in ['nan', 'none', 'null', '']:
                    condition = val
                    
            graded_col = col_map.get('grade', col_map.get('graded'))
            if graded_col:
                g_val = str(row[graded_col]).strip()
                if g_val and g_val.lower() not in ['nan', 'none', 'null', 'false', 'no', '', 'ungraded']:
                    is_graded = True
                    if g_val.lower() not in ['yes', 'true', 'graded']:
                        condition = g_val
                    else:
                        bgs_col = col_map.get('bgs', col_map.get('bgs grade'))
                        if bgs_col:
                            b_val = str(row[bgs_col]).strip()
                            if b_val and b_val.lower() not in ['nan', 'none', 'null', '']:
                                condition = f"BGS {b_val}"

            if is_sealed:
                card_type = "Sealed"
            elif is_graded:
                card_type = "Graded"
            else:
                card_type = "Single"

            items = db_session.query(InventoryItem).filter(
                InventoryItem.name == raw_name,
                InventoryItem.set_name == raw_set,
                InventoryItem.sequence_number == raw_number
            ).all()
            
            if items:
                for item in items:
                    item.condition = condition
                    item.card_type = card_type
                    item.game = game
                updated_count += len(items)
            else:
                not_found_count += 1
                
        except Exception as e:
            print(f"[!] Error patching row {index}: {e}")
            
    db_session.commit()
    return updated_count, not_found_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import cards from CSV to inventory")
    parser.add_argument("csv_file", help="Path to the export.csv file")
    args = parser.parse_args()
    process_csv_import(args.csv_file)
