import csv
import os
import time
import re
import sqlite3
import json
import traceback
from io import BytesIO
import queue
import threading

import barcode
from tkinter import messagebox
import pyperclip
from barcode.writer import ImageWriter
from PIL import Image  # Keep PIL.Image for barcode and general image handling

from rapidfuzz import fuzz
import requests as _requests
from config import AUTO_PRINT_LABELS, DEBUG_MODE

from database import db_session, StoreSettings, SystemSettings, InventoryItem, StagingItem
from api_client import PokemonAPI

def calculate_shop_price(market_price: float) -> float:
    from database import db_session, SystemSettings
    settings = db_session.query(SystemSettings).first()
    if not settings:
        return market_price
        
    base_price = market_price
    
    # 1. Apply Markup
    if settings.markup_type == "Percentage (%)":
        base_price = base_price * (1 + (settings.markup_value / 100))
    elif settings.markup_type == "Flat Amount ($)":
        base_price = base_price + settings.markup_value
        
    # 2. Apply Rounding
    import math
    if settings.rounding_rule == "Round to nearest .99":
        # Ceil to nearest integer, then subtract 0.01
        return math.ceil(base_price) - 0.01
    elif settings.rounding_rule == "Round to nearest .50":
        # Round to nearest 0.50
        return round(base_price * 2) / 2
    else:
        # Exact/None
        return round(base_price, 2)

def apply_trade_values_to_staging(pending_trade_id_list: list) -> tuple:
    """
    Weighted Cost Distribution: Distributes total cash paid across all staging items
    proportionally by market value, then promotes them all to inventory.

    Args:
        pending_trade_id_list: List of PendingTrade IDs to apply.

    Returns:
        (success: bool, message: str)
    """
    from database import PendingTrade, StagingItem, InventoryItem, PurchaseRecord, SyncOutbox
    try:
        # 1. Fetch and sum cash paid from selected PendingTrade records
        trades = db_session.query(PendingTrade).filter(
            PendingTrade.id.in_(pending_trade_id_list),
            PendingTrade.status == 'pending'
        ).all()

        if not trades:
            return False, "No valid pending trades found with the given IDs."

        sum_cash_paid = sum(t.total_cash_paid for t in trades)

        # 2. Load all staging items and compute total staging market value
        staging_items = db_session.query(StagingItem).all()
        if not staging_items:
            return False, "No items in the Staging Dock to apply trade values to."

        total_staging_mkt = sum(
            (item.market_price or 0.0) * (item.quantity or 1) for item in staging_items
        )

        if total_staging_mkt <= 0:
            return False, "Total staging market value is zero — cannot distribute cost basis."

        # 3. Calculate cost basis per staging item and promote to inventory
        success_count = 0
        error_count = 0

        for staging_item in staging_items:
            try:
                item_mkt = (staging_item.market_price or 0.0) * (staging_item.quantity or 1)
                weight = item_mkt / total_staging_mkt
                total_item_cost = sum_cash_paid * weight
                cost_per_unit = round(total_item_cost / (staging_item.quantity or 1), 2)

                # Merge into existing inventory item if it exists
                existing_item = db_session.query(InventoryItem).filter(
                    InventoryItem.name == staging_item.name,
                    InventoryItem.set_name == staging_item.set_name,
                    InventoryItem.sequence_number == staging_item.sequence_number,
                    InventoryItem.variant == staging_item.variant,
                    InventoryItem.condition == staging_item.condition
                ).first()

                shop_price = calculate_shop_listing_price(staging_item.market_price or 0.0, staging_item.card_type)
                new_sticker_price = staging_item.suggested_price

                if existing_item:
                    total_qty = existing_item.stock + (staging_item.quantity or 1)
                    if total_qty > 0:
                        new_avg_cost = (
                            (existing_item.cost * existing_item.stock) +
                            (cost_per_unit * (staging_item.quantity or 1))
                        ) / total_qty
                        existing_item.cost = round(new_avg_cost, 2)
                    existing_item.stock = total_qty
                    existing_item.price = staging_item.market_price or existing_item.price
                    existing_item.shop_listing_price = shop_price
                    existing_item.sticker_price = new_sticker_price
                    if not existing_item.image_url and staging_item.image_path:
                        existing_item.image_url = staging_item.image_path
                    db_session.add(SyncOutbox(
                        action_type='stock_update', sku=existing_item.sku,
                        quantity_change=staging_item.quantity or 1, new_price=0.0
                    ))
                    db_session.add(SyncOutbox(
                        action_type='price_update', sku=existing_item.sku,
                        quantity_change=0, new_price=shop_price
                    ))
                    db_session.add(PurchaseRecord(
                        sku=existing_item.sku,
                        quantity=staging_item.quantity or 1,
                        cost_per_unit=cost_per_unit
                    ))
                else:
                    new_inv = InventoryItem(
                        sku=staging_item.sku,
                        name=staging_item.name,
                        set_name=staging_item.set_name,
                        sequence_number=staging_item.sequence_number,
                        cost=cost_per_unit,
                        price=staging_item.market_price or 0.0,
                        shop_listing_price=shop_price,
                        sticker_price=new_sticker_price,
                        card_type=staging_item.card_type,
                        variant=staging_item.variant,
                        condition=staging_item.condition,
                        stock=staging_item.quantity or 1,
                        image_url=staging_item.image_path
                    )
                    db_session.add(new_inv)
                    db_session.add(PurchaseRecord(
                        sku=new_inv.sku,
                        quantity=new_inv.stock,
                        cost_per_unit=cost_per_unit
                    ))

                db_session.delete(staging_item)
                success_count += 1
            except Exception as e:
                print(f"[apply_trade_values] Error promoting {staging_item.sku}: {e}")
                error_count += 1

        # 4. Mark trades as applied
        for trade in trades:
            trade.status = 'applied'

        db_session.commit()

        msg = (
            f"Applied {len(trades)} trade(s) (${sum_cash_paid:.2f} total cost) across "
            f"{success_count} staging items. Errors: {error_count}."
        )
        print(f"[apply_trade_values] {msg}")
        return True, msg

    except Exception as e:
        db_session.rollback()
        return False, f"Fatal error during trade application: {e}"


# Singleton API client instance (avoids reinitializing requests.Session per call)
_pokemon_api = PokemonAPI()

# Windows-specific clipboard handling for images
try:
    import win32clipboard
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# Global cache for duplication prevention
scraped_signatures = set()

# Asynchronous Background Worker Queues
input_queue = queue.Queue()
output_queue = queue.Queue()

def start_background_worker(core_manager):
    """Boots the CoreManager's Shopify sync outbox. OCR pipeline has been removed."""
    print("[*] Background worker started (Shopify sync outbox active).")

def get_card_signature(name, set_name, sequence_number, variant, condition):
    """Generates a unique tracking signature for a card for duplication prevention."""
    return f"{name}_{set_name}_{sequence_number}_{variant}_{condition}".lower().strip()

def remove_signature_from_cache(name, set_name, sequence_number, variant, condition):
    """Removes a signature from the global cache to allow re-scanning."""
    sig = get_card_signature(name, set_name, sequence_number, variant, condition)
    scraped_signatures.discard(sig)

def clear_signatures_cache():
    """Clears the session tracking cache."""
    scraped_signatures.clear()



def add_item_to_staging(data, refresh_callback=None):
    """
    Natively adds a card to the staging queue.
    Checks for SKU reuse from Inventory and merges duplicates already in Staging.
    'data' dict keys: name, set_name, sequence_number, variant, condition, card_type, market_price, quantity, image_path, sku (optional)
    """
    settings = db_session.query(SystemSettings).first()
    rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
    
    import re
    def normalize_string(s):
        return re.sub(r'[^a-z0-9]', '', str(s).lower()) if s else ""
        
    inv_candidates = db_session.query(InventoryItem).filter(
        InventoryItem.set_name == data['set_name'],
        InventoryItem.sequence_number == data['sequence_number'],
        InventoryItem.variant == data['variant'],
        InventoryItem.condition == data['condition'],
        InventoryItem.card_type == data['card_type']
    ).all()
    
    existing_inv = next((c for c in inv_candidates if normalize_string(c.name) == normalize_string(data['name'])), None)

    if existing_inv:
        target_sku = existing_inv.sku
    else:
        target_sku = data.get('sku')
        if not target_sku or db_session.query(InventoryItem).filter_by(sku=target_sku).first() or db_session.query(StagingItem).filter_by(sku=target_sku).first():
            target_sku = f"CS-{os.urandom(2).hex().upper()}"
            while db_session.query(InventoryItem).filter_by(sku=target_sku).first() or db_session.query(StagingItem).filter_by(sku=target_sku).first():
                target_sku = f"CS-{os.urandom(2).hex().upper()}"

    if data.get('image_path') and os.path.exists(data['image_path']):
        thumb_path = os.path.join('static', 'scraped_thumbnails', f"{target_sku}.png")
        if data['image_path'] != thumb_path:
            try:
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                import shutil
                shutil.copy(data['image_path'], thumb_path)
                data['image_path'] = thumb_path
            except Exception as e:
                print(f"Failed to copy thumbnail to target_sku: {e}")

    # 2. Check if this exact item is already in the Staging Queue
    staging_candidates = db_session.query(StagingItem).filter(
        StagingItem.set_name == data['set_name'],
        StagingItem.sequence_number == data['sequence_number'],
        StagingItem.variant == data['variant'],
        StagingItem.condition == data['condition'],
        StagingItem.card_type == data['card_type']
    ).all()
    
    existing_staging = next((c for c in staging_candidates if normalize_string(c.name) == normalize_string(data['name'])), None)

    if existing_staging:
        # --- Multi-Sample Consensus Engine ---
        meta = json.loads(existing_staging.ocr_metadata or '{}')
        scores = meta.setdefault('scores', {})
        votes = meta.setdefault('votes', {})
        history = meta.setdefault('history', [])
        flags = meta.setdefault('flags', {})
        
        new_scores = data.get('confidence_scores', {})
        if new_scores is None: # Manual override fallback
            new_scores = {f: 100 for f in ['market_price', 'name', 'set_name']}

        # Add current scan to history
        history.append({
            "timestamp": time.time(),
            "price": data.get('market_price'),
            "scores": new_scores
        })

        updated = False
        for field in ['market_price', 'name', 'set_name']:
            if field not in data: continue
            val = data[field]
            
            field_votes = votes.setdefault(field, {})
            v_str = str(val)
            field_votes[v_str] = field_votes.get(v_str, 0) + 1
            
            new_conf = new_scores.get(field, 0)
            old_conf = scores.get(field, 0)

            # Intake Logic Gate: Check for >50% price variance
            if field == 'market_price' and existing_staging.market_price > 0:
                variance = abs(val - existing_staging.market_price) / existing_staging.market_price
                if variance > 0.50:
                    flags[field] = "TOMATO" # Variance Trigger
                    existing_staging.needs_review = True
                elif new_conf < 85 or len(field_votes) > 1:
                    flags[field] = "GOLD" # Low confidence or inconsistency

            # Weighted Consensus: Higher confidence scan wins
            if new_conf > old_conf:
                setattr(existing_staging, field, val)
                scores[field] = new_conf
                updated = True
            elif new_conf == old_conf and old_conf > 0:
                mode_val = max(field_votes, key=field_votes.get)
                typed_val = float(mode_val) if field == 'market_price' else mode_val
                if getattr(existing_staging, field) != typed_val:
                    setattr(existing_staging, field, typed_val)
                    updated = True

        if updated:
            existing_staging.suggested_price = calculate_suggested_price(existing_staging.market_price, rule)
            existing_staging.cost_basis = round(existing_staging.market_price * (settings.buy_percentage if settings else 0.7), 2)
            # Clear review flag if confidence recovers
            if scores.get('name', 0) >= 85 and flags.get('market_price') != "TOMATO":
                existing_staging.needs_review = False

        meta['flags'] = flags
        meta['history'] = history[-10:] # Keep last 10 samples
        existing_staging.ocr_metadata = json.dumps(meta)
        if data.get('image_path'):
            existing_staging.image_path = data['image_path']
        # Explicitly ensure that the quantity of that staging item remains exactly as it was (do not execute quantity += 1)
        db_session.commit()
        print(f"[*] Consensus updated {data['name']} (Flag: {flags.get('market_price', 'NONE')})")
    else:
        initial_meta = {
            "scores": data.get('confidence_scores', {}),
            "votes": {f: {str(data[f]): 1} for f in ['market_price', 'name', 'set_name'] if f in data},
            "flags": {"market_price": "GOLD" if data.get('confidence_scores', {}).get('market_price', 0) < 85 else "NONE"},
            "history": [{"timestamp": time.time(), "price": data.get('market_price'), "scores": data.get('confidence_scores', {})}]
        }
        # Create new staging entry (potentially using old SKU)
        new_item = StagingItem(
            name=data['name'],
            set_name=data['set_name'],
            sequence_number=data['sequence_number'],
            market_price=data['market_price'],
            suggested_price=calculate_suggested_price(data['market_price'], rule),
            cost_basis=data.get('cost_basis', round(data['market_price'] * (settings.buy_percentage if settings else 0.7), 2)),
            card_type=data.get('card_type', 'Unknown'),
            variant=data['variant'],
            condition=data['condition'],
            quantity=data['quantity'],
            sku=target_sku,
            image_path=data.get('image_path'),
            needs_review=data.get('needs_review', False),
            ocr_metadata=json.dumps(initial_meta),
            game=data.get('game', 'Pokemon')
        )
        db_session.add(new_item)
        db_session.commit()
        if AUTO_PRINT_LABELS:
            generate_item_barcode(target_sku)
            print_barcode_to_label_printer(target_sku)
        
        if DEBUG_MODE:
            print(f"[*] Committed {data['name']} to staging (SKU: {target_sku}).")
    
    if refresh_callback:
        refresh_callback()

def save_scraped_item(data, refresh_callback=None):
    """Commits a parsed item to the StagingItem SQLite table."""
    add_item_to_staging(data, refresh_callback)

def process_captured_data(raw_data_string):
    """
    Parses raw text into card details.
    Example format: 'Charizard 004/102 Base Set $34.99'
    """
    raw_data_string = raw_data_string.strip()
    
    # Attempt to parse using regex for common card formats
    # This regex tries to capture:
    # 1. Card Name (anything before a potential set/sequence number or price)
    # 2. Set Number (e.g., 123/456, 001/025, SWSH01, POGO 030)
    # 3. Market Value (e.g., $34.99, 34.99)
    
    # Pattern: (Card Name) (Set Name/Sequence Number) ($Price)
    # Example: "Charizard 004/102 Base Set $34.99"
    # Example: "Mewtwo V POGO 030 $15.00"
    # Example: "Pikachu VMAX SWSH06 $20.00"
    
    # Regex breakdown:
    # (.*?) - Non-greedy match for card name
    # (?: (\w+\s*\d+/\d+|\w+\d+))? - Optional non-capturing group for set/sequence (e.g., 004/102, POGO 030, SWSH06)
    # (?: \$\s*(\d+\.?\d*))?$ - Optional non-capturing group for price at the end
    
    match = re.search(r"^(.*?)(?: (\w+\s*\d+/\d+|\w+\d+))?(?: \$\s*(\d+\.?\d*))?$", raw_data_string, re.IGNORECASE)
    
    name = "Unknown Card"
    set_number = "N/A"
    market_value = 0.0
    
    if match:
        name = match.group(1).strip() if match.group(1) else "Unknown Card"
        set_number = match.group(2).strip() if match.group(2) else "N/A"
        try:
            market_value = float(match.group(3)) if match.group(3) else 0.0
        except ValueError:
            market_value = 0.0
    return {
        "name": name or "Unknown Card",
        "market_value": market_value,
        "sequence_number": set_number
    }

def calculate_profit_margin(cost, price):
    """Calculates the percentage margin for an item."""
    if price <= 0:
        return 0
    return round(((price - cost) / price) * 100, 2)

def calculate_batch_costs(total_market_value, total_price_paid, card_list):
    """
    Calculates the effective cost of individual cards bought in a bulk lot.
    purchase_rate = Price Paid / Total Market Value
    effective_cost = Individual Market Value * Purchase Rate
    """
    if total_market_value <= 0:
        return []

    effective_purchase_rate = total_price_paid / total_market_value
    
    processed_cards = []
    for card in card_list:
        # Calculate proportional cost based on market value
        market_val = card.get('market_value', 0)
        effective_cost = round(market_val * effective_purchase_rate, 2)
        
        card_entry = card.copy()
        card_entry['effective_cost'] = effective_cost
        processed_cards.append(card_entry)
        
    return processed_cards

def calculate_buy_cost(market_value, method='cash'):
    """
    Calculates the purchase price (basis cost) for the shop.
    Rules: 70% for Cash, 80% for Trade Credit.
    """
    settings = db_session.query(SystemSettings).first()
    buy_rate = settings.buy_percentage if settings else 0.70
    trade_rate = settings.trade_percentage if settings else 0.80
    
    rate = buy_rate if method == 'cash' else trade_rate
    return round(market_value * rate, 2)

def calculate_partial_trade(incoming_card_market, outgoing_card_market, buy_rate=0.7, trade_rate=0.8):
    """
    Calculates the cash difference for a trade-in deal.
    Default rules: 70% buy rate for customers, 80% value for shop trade items.
    Returns the cash amount required to close the deal (Buy Price - Trade Value).
    """
    buy_price = incoming_card_market * buy_rate
    trade_value = outgoing_card_market * trade_rate
    
    # Round to two decimal places for currency
    return round(buy_price - trade_value, 2)

def calculate_net_profit(sold_price, effective_cost):
    """
    Returns the net profit after a sale.
    """
    return round(sold_price - effective_cost, 2)

def generate_label(sku, format='QR'):
    """
    Generates a label image for the given SKU.
    format: 'QR' or 'Barcode'
    Returns a PIL Image object sized suitably for a 13mm label.
    """
    from PIL import Image
    
    # 13mm at 300 DPI is approx 153 pixels. We target 150x150 for QR, 300x150 for Barcode
    if format.upper() == 'QR':
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=1,
        )
        qr.add_data(str(sku))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").get_image()
        img = img.resize((150, 150), Image.Resampling.LANCZOS)
        return img
    elif format.lower() == 'barcode':
        import barcode
        from barcode.writer import ImageWriter
        from io import BytesIO
        
        code_class = barcode.get_barcode_class('code128')
        writer = ImageWriter()
        my_barcode = code_class(str(sku), writer=writer)
        
        fp = BytesIO()
        my_barcode.write(fp)
        fp.seek(0)
        img = Image.open(fp)
        img = img.resize((300, 150), Image.Resampling.LANCZOS)
        return img
    else:
        raise ValueError("Unsupported format. Use 'QR' or 'Barcode'.")

def generate_item_barcode(sku, market_price=None, format='QR'):
    """
    Legacy wrapper that generates a label and saves it to disk for the UI/Printer to use.
    Now defaults to QR.
    """
    try:
        img = generate_label(sku, format=format)
        base_path = os.path.dirname(os.path.abspath(__file__))
        barcode_dir = os.path.join(base_path, 'static', 'barcodes')
        
        if not os.path.exists(barcode_dir):
            os.makedirs(barcode_dir)

        file_path = os.path.join(barcode_dir, f"{sku}.png")
        img.save(file_path)
        return file_path
    except Exception as e:
        print(f"Barcode Generation Error: {e}")
        return str(e)

def print_barcode_to_label_printer(sku):
    """
    Desktop-Specific: Sends the generated barcode image to the Windows Default Label Printer.
    This function is intended for manual triggering via UI.
    """
    # Define the path relative to this file
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, 'static', 'barcodes', f"{sku}.png")
    
    if not os.path.exists(file_path):
        print(f"ERROR: Barcode image not found for SKU {sku} at {file_path}")
        return False
    
    try:
        # On Windows, os.startfile with "print" verb attempts to print the file
        # This relies on the default application for .png files having a print verb.
        # DEACTIVATED: Automated spooling is disabled per safety requirements.
        # os.startfile(file_path, "print") 
        print(f"[*] Sent barcode for SKU {sku} to default printer.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to send barcode for SKU {sku} to printer: {e}")
        # Fallback for non-Windows or if "print" verb fails
        # For more robust printing, consider pywin32 or dedicated printer libraries.
        return False

def apply_rounding(value, rule='no_rounding'):
    """Applies specific rounding rules for pricing."""
    if rule == "Round Up to Nearest $1.00":
        import math
        return float(math.ceil(value))
    elif rule == "Round to Nearest $1.00":
        import math
        return float(math.ceil(value)) # Kept for backward compatibility
    elif rule == "Round to Nearest $0.95 Cents":
        return float(int(value)) + 0.95
    return round(value, 2)

def calculate_suggested_price(market_value, rule="Keep Raw TCG Decimal Payouts", multiplier=1.00):
    """Computes target price suggestions based on system parameters."""
    return apply_rounding(market_value * multiplier, rule)

def calculate_shop_listing_price(market_price, card_type="Single"):
    """
    Computes final Shopify listing price using shipping/padding rules, Shopify markup, and Shopify rounding rules.
    """
    from database import db_session, SystemSettings
    padded_price = market_price
    try:
        from database import ShippingRule
        rules = db_session.query(ShippingRule).filter(ShippingRule.card_type == card_type).all()
        for rule in rules:
            if rule.min_price <= market_price <= rule.max_price:
                padded_price = market_price + rule.additional_cost
                break
    except Exception as e:
        pass
        
    return calculate_shop_price(padded_price)

def calculate_lot_sale_distribution(items, negotiated_total):
    """
    Apportions a negotiated lot price across multiple items based on their market value weights.
    Returns a list of tuples: (item, apportioned_price, profit)
    """
    total_market_value = sum(it.price for it in items)
    if total_market_value <= 0: return []
    
    distribution = []
    for it in items:
        # Step B: Value weight share contribution
        weight = it.price / total_market_value
        # Step C: Apportioned sale payout assignment
        apportioned_price = round(negotiated_total * weight, 2)
        # Step D: True independent Net Profit (Payout - cost basis)
        profit = round(apportioned_price - it.cost, 2)
        distribution.append((it, apportioned_price, profit))
    return distribution

def sync_staging_queue_to_settings():
    """Iterates through unprinted staging items and updates values based on current settings."""
    settings = db_session.query(SystemSettings).first()
    if not settings: return
    
    staging_items = db_session.query(StagingItem).all()
    for item in staging_items:
        item.suggested_price = calculate_suggested_price(item.market_price, settings.rounding_strategy)
        # Update cost basis based on the default cash rate
        item.cost_basis = round(item.market_price * settings.buy_percentage, 2)
    
    db_session.commit()

def copy_text_to_clipboard(text):
    """Natively writes raw strings to the local system clipboard."""
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        print(f"Clipboard Error: {e}")
        return False

def confirm_intake(card_data):
    """
    Parses raw OCR dictionary and prepares JSON for database.
    Expected keys: name, set_info, market_value
    """
    from database import db_session, SystemSettings
    settings = db_session.query(SystemSettings).first()
    rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"

    # Ensure value is clean
    market_val = float(str(card_data.get('market_value', 0)).replace('$', '').replace(',', ''))
    suggested_price = calculate_suggested_price(market_val, rule=rounding_rule)
    # Calculate the strict cost basis (defaulting to cash rule)
    cost_basis = calculate_buy_cost(market_val, method='cash')
    
    return {
        "name": card_data.get('name', 'Unknown Item'),
        "sku": f"CS-{os.urandom(2).hex().upper()}",
        "market_value": round(market_val, 2),
        "suggested_price": suggested_price,
        "cost_basis": cost_basis,
        "sequence_number": card_data.get('sequence_number', 'N/A'),
        "set_name": card_data.get('set_name', 'N/A'),
        "variant": card_data.get('variant', 'Standard'), # Ensure variant is passed
        "condition": card_data.get('condition', 'Near Mint'), # Ensure condition is passed
        "quantity": card_data.get('quantity', 1) # Ensure quantity is passed
    }

def parse_collectr_csv(file_path):
    """Parses Collectr CSV export based on specified column mapping."""
    import pandas as pd
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[!] Failed to parse CSV: {e}")
        return []

    df.columns = [str(c).strip() for c in df.columns]
    col_map = {str(c).lower(): str(c) for c in df.columns}
    
    name_col = col_map.get('product name', col_map.get('name'))
    set_col = col_map.get('set', col_map.get('set name'))
    num_col = col_map.get('card number', col_map.get('number', col_map.get('sequence_number')))
    
    market_price_col = None
    for c in col_map.keys():
        if 'market price' in c or 'market value' in c or 'market_value' in c or 'price' in c or 'value' in c:
            market_price_col = col_map[c]
            break
            
    qty_col = col_map.get('quantity', col_map.get('qty'))
    
    results = []
    for index, row in df.iterrows():
        try:
            name = str(row[name_col]).strip() if name_col else "Unknown"
            set_name = str(row[set_col]).strip() if set_col else "N/A"
            seq_num = str(row[num_col]).strip() if num_col and str(row[num_col]).lower() != 'nan' else "N/A"
            if seq_num == "": seq_num = "N/A"
            
            # Collectr often appends the sequence number to the card name. Strip it to prevent duplicates.
            if seq_num != "N/A":
                if name.endswith(f" - {seq_num}"):
                    name = name[:-(len(seq_num) + 3)].strip()
                else:
                    # Sometimes sequence number is 167 but Collectr name is 167/159
                    import re
                    match = re.search(r' - (\w+/\w+)$', name)
                    if match and match.group(1).startswith(seq_num):
                        name = name[:match.start()].strip()
                        seq_num = match.group(1) # Use the full sequence number from the name
            
            qty = 0
            if qty_col:
                try: qty = int(row[qty_col])
                except: qty = 0
                
            mv = 0.0
            if market_price_col:
                try:
                    p_str = str(row[market_price_col]).strip().replace('$', '').replace(',', '')
                    if p_str.lower() not in ['nan', 'none', 'null', '', 'n/a', '-']:
                        mv = float(p_str)
                except: mv = 0.0
                
            results.append({
                'name': name,
                'set_name': set_name,
                'sequence_number': seq_num,
                'market_value': mv,
                'quantity': qty
            })
        except Exception:
            continue
    return results

def run_reconciliation_audit(csv_data):
    """Cross-references CSV data against local SQLite InventoryItem table."""
    from rapidfuzz import fuzz
    import re
    
    def normalize_name(s):
        return re.sub(r'[^a-z0-9]', '', str(s).lower()) if s else ""
        
    def normalize_seq(s):
        if not s: return ""
        s = str(s).lower()
        def repl(m):
            return m.group(0).lstrip('0') or '0'
        s = re.sub(r'\d+', repl, s)
        return re.sub(r'[^a-z0-9]', '', s)

    db_items = db_session.query(InventoryItem).all()
    settings = db_session.query(SystemSettings).first()
    threshold = settings.price_fluctuation_threshold if settings else 0.10
    
    db_lookup = {}
    for it in db_items:
        key = (normalize_name(it.name), normalize_seq(it.sequence_number))
        if key not in db_lookup:
            db_lookup[key] = {'stock': 0, 'price': it.price, 'items': [], 'orig_name': it.name, 'orig_seq': it.sequence_number}
        db_lookup[key]['stock'] += it.stock
        db_lookup[key]['items'].append(it)

    csv_lookup = {}
    csv_row_examples = {}
    
    for row in csv_data:
        norm_name = normalize_name(row['name'])
        norm_seq = normalize_seq(row['sequence_number'])
        key = (norm_name, norm_seq)
        
        if key not in db_lookup:
            # Fallback fuzzy matching by sequence number
            best_match_key = None
            best_score = 0
            if norm_seq != "":
                for k in db_lookup.keys():
                    if k[1] == norm_seq:
                        score = fuzz.token_sort_ratio(norm_name, k[0])
                        if score >= 80 and score > best_score:
                            best_score = score
                            best_match_key = k
            if best_match_key:
                key = best_match_key
                
        csv_lookup[key] = csv_lookup.get(key, 0) + row['quantity']
        if key not in csv_row_examples:
            csv_row_examples[key] = row

    removal, intake, volatility = [], [], []
    for key, total_csv_qty in csv_lookup.items():
        db_entry = db_lookup.get(key)
        row = csv_row_examples[key]
        
        if not db_entry:
            # If completely missing from DB, try to find a fallback SKU by name for the image
            from database import InventoryItem as InvItem # Alias to prevent shadowing
            import database
            fallback_item = database.db_session.query(InvItem).filter(InvItem.name.ilike(f"%{row['name']}%")).first()
            sku = fallback_item.sku if fallback_item else None
            intake.append({'name': row['name'], 'sequence_number': row['sequence_number'], 'qty_to_add': total_csv_qty, 'sku': sku})
        else:
            sku = db_entry['items'][0].sku if db_entry['items'] else None
            if total_csv_qty > db_entry['stock']:
                removal.append({**row, 'qty_to_remove': total_csv_qty - db_entry['stock'], 'sku': sku})
            if db_entry['price'] > 0:
                if abs(row['market_value'] - db_entry['price']) / db_entry['price'] > threshold:
                    suggested = calculate_suggested_price(row['market_value'])
                    if suggested != db_entry['price']:
                        for it in db_entry['items']: 
                            it.old_price = it.price
                            it.needs_update = True
                        volatility.append({**row, 'old_price': db_entry['price'], 'items': db_entry['items'],
                                           'suggested': suggested})
    db_session.commit()

    for key, entry in db_lookup.items():
        csv_qty = csv_lookup.get(key, 0)
        if entry['stock'] > csv_qty:
            sku = entry['items'][0].sku if entry['items'] else None
            set_name = entry['items'][0].set_name if entry['items'] else ""
            intake.append({'name': entry['orig_name'], 'set_name': set_name, 'sequence_number': entry['orig_seq'], 'qty_to_add': entry['stock'] - csv_qty, 'sku': sku})
            
    return removal, intake, volatility

def copy_barcode_to_clipboard(sku):
    """
    Windows-Specific: Copies the generated barcode image to the system clipboard.
    """
    if not HAS_WIN32:
        print("Error: pywin32 not installed. Cannot copy image to clipboard.")
        return False
        
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'barcodes', f"{sku}.png")
    if not os.path.exists(file_path):
        return False

    image = Image.open(file_path)
    output = BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()
    return True

def reconcile_databases(uploaded_db_path):
    """
    Compares the uploaded database against the current local database.
    Identifies items sold on the mobile device and new intake items.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_db_path = os.path.join(base_dir, 'card_shop.db')
    if not os.path.exists(local_db_path):
        return {'sold': [], 'new': []}

    summary = {'sold': [], 'new': []}
    conn_local = None
    conn_remote = None

    try:
        conn_local = sqlite3.connect(local_db_path)
        conn_remote = sqlite3.connect(uploaded_db_path)
        
        # Get local inventory state
        local_items = {row[0]: row[1] for row in 
                       conn_local.execute("SELECT sku, stock FROM inventory_item").fetchall()}
        
        # Get remote inventory state
        remote_cursor = conn_remote.execute("SELECT sku, name, cost, price, stock FROM inventory_item")
        remote_items = {}
        for row in remote_cursor:
            remote_items[row[0]] = {
                'sku': row[0], 'name': row[1], 'cost': row[2], 
                'price': row[3], 'stock': row[4]
            }

        # 1. Identify Sold: In local with stock > 0, but in remote with stock <= 0
        for sku, stock in local_items.items():
            if stock > 0 and sku in remote_items:
                if remote_items[sku]['stock'] <= 0:
                    summary['sold'].append({'sku': sku, 'name': remote_items[sku]['name']})

        # 2. Identify New Intake: In remote but not in local
        for sku, item in remote_items.items():
            if sku not in local_items:
                summary['new'].append(item)
    except sqlite3.Error as e:
        print(f"Database Reconciliation Error: {e}")
    finally:
        if conn_local: conn_local.close()
        if conn_remote: conn_remote.close()

    return summary

def manual_api_refetch(item_id, updated_name, updated_set, updated_number):
    """
    Manually re-queries the Pokemon TCG API for a staging item using corrected name, set, and number.
    Updates the staging item in the database, preserving the user's manual inputs for name and number.
    Downloads the high-resolution image only if the API result is securely verified.
    """
    # 1. Fetch staging item from DB
    staging_item = db_session.query(StagingItem).filter(StagingItem.id == item_id).first()
    if not staging_item:
        print(f"[API Refetch] Staging item {item_id} not found.")
        return False

    local_name = updated_name.strip()
    local_seq = _pokemon_api._sanitize_sequence_number(updated_number)

    print(f"[API Refetch] Re-fetching card data for name='{local_name}', set='{updated_set}', number='{local_seq}'")
    
    # Apply manual changes to database first, so they are saved regardless of API outcomes
    staging_item.name = local_name
    staging_item.set_name = updated_set.strip().title()
    staging_item.sequence_number = local_seq

    try:
        # 1. Check local DB (card_images.db) first
        import sys, os
        img_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image_db_manager')
        if img_db_path not in sys.path:
            sys.path.append(img_db_path)
        import db_handler as img_db_handler

        local_img = img_db_handler.find_image_by_set_and_number(updated_set.strip(), local_seq, card_name=local_name)
        if local_img:
            print(f"[API Refetch] Found image in local DB -> {local_img}")
            hires_url = local_img
            name_score = 100
            api_name = local_name
            api_result = {"clean_name": local_name, "high_res_image": local_img}
        else:
            # Fallback to PokemonAPI client
            api_result = _pokemon_api.fetch_card_data(updated_set, updated_number, card_name=local_name)

        if api_result:
            # Secure verification check for image/price replacement
            if not local_img:
                api_name = api_result.get("clean_name", "")
                name_score = fuzz.WRatio(local_name.lower(), api_name.lower())
                hires_url = api_result.get("high_res_image")
            
            if api_name and api_name.lower() != local_name.lower():
                print(f"[API Refetch] Suggested Correction: API returned '{api_name}' for local '{local_name}'")
                
            if name_score >= 80:
                print(f"[API Refetch] Secure match verified (score={name_score:.0f}%). Updating image.")

                # Download high-res image
                if hires_url:
                    thumb_path = staging_item.image_path
                    # If no thumbnail path exists, generate a new one
                    if not thumb_path or not os.path.exists(thumb_path):
                        sku = staging_item.sku or f"CS-{os.urandom(2).hex().upper()}"
                        thumb_path = os.path.join('static', 'scraped_thumbnails', f"{sku}.png")
                        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                        staging_item.image_path = thumb_path

                    try:
                        if hires_url.startswith('http'):
                            img_resp = _requests.get(hires_url, timeout=10)
                            img_resp.raise_for_status()
                            with open(thumb_path, 'wb') as f:
                                f.write(img_resp.content)
                            print(f"[API Refetch] Downloaded hi-res image -> {thumb_path}")
                        elif os.path.exists(hires_url):
                            import shutil
                            shutil.copyfile(hires_url, thumb_path)
                            print(f"[API Refetch] Copied local hi-res image -> {thumb_path}")
                    except Exception as img_err:
                        print(f"[API Refetch] Image download/copy failed: {img_err}")
            else:
                print(f"[API Refetch] API match '{api_name}' could not be securely verified against manual entry '{local_name}' (score={name_score:.0f}%). Keeping existing image.")
        else:
            print("[API Refetch] No card found from TCG API. Keeping manual edits and existing image.")
            
        db_session.commit()
        print(f"[API Refetch] Success: '{staging_item.name}'")
        return True
    except Exception as e:
        db_session.rollback()
        print(f"[API Refetch] Error during refetch: {e}")
        traceback.print_exc()
        return False

def get_card_by_barcode(barcode):
    """Searches the SQLite inventory table for a matching sku/barcode."""
    from database import db_session, InventoryItem
    return db_session.query(InventoryItem).filter_by(sku=barcode).first()

def recalculate_cart_totals(cart_items, sale_price_input=None, percentage_input=None):
    """
    Calculates the 'Target Sale Price' based on the total market value of all items in the cart.
    Allows overriding sale price to recalculate percentage, or overriding percentage to recalculate sale price.
    """
    total_market_value = 0.0
    for item in cart_items:
        if isinstance(item, dict) and 'item' in item:
            item_obj = item['item']
        else:
            item_obj = item
        item_val = getattr(item_obj, 'price', item_obj.get('price', 0.0)) if hasattr(item_obj, 'price') else item_obj.get('price', 0.0)
        total_market_value += float(item_val)
    
    if total_market_value <= 0:
        return 0.0, 0.0, 0.0

    target_sale_price = total_market_value
    percentage = 100.0

    if sale_price_input is not None and str(sale_price_input).strip() != "":
        target_sale_price = float(sale_price_input)
        percentage = (target_sale_price / total_market_value) * 100.0
    elif percentage_input is not None and str(percentage_input).strip() != "":
        percentage = float(percentage_input)
        target_sale_price = total_market_value * (percentage / 100.0)

    return total_market_value, round(target_sale_price, 2), round(percentage, 2)

def finalize_sale(cart_items, final_sale_price, payment_method):
    """
    For each item in the cart:
    - Update inventory quantity (reduce stock by 1)
    - Record sale_price and payment_method in Sales Log.
    Apportions the final_sale_price proportionally based on market values.
    """
    from database import db_session, Sale, InventoryItem, SyncOutbox
    
    total_market_value = 0.0
    for item in cart_items:
        if isinstance(item, dict) and 'item' in item:
            item_obj = item['item']
        else:
            item_obj = item
        item_val = getattr(item_obj, 'price', item_obj.get('price', 0.0)) if hasattr(item_obj, 'price') else item_obj.get('price', 0.0)
        total_market_value += float(item_val)

    try:
        # Offline-First Sync Outbox Phase
        for item in cart_items:
            item_obj = item['item'] if isinstance(item, dict) and 'item' in item else item
            item_sku = getattr(item_obj, 'sku', item_obj.get('sku', 'Unknown')) if hasattr(item_obj, 'sku') else item_obj.get('sku', 'Unknown')
            
            outbox = SyncOutbox(action_type='sale', sku=item_sku, quantity_change=-1)
            db_session.add(outbox)

        # Local Checkout Phase
        for item in cart_items:
            if isinstance(item, dict) and 'item' in item:
                item_obj = item['item']
            else:
                item_obj = item
                
            item_price = getattr(item_obj, 'price', item_obj.get('price', 0.0)) if hasattr(item_obj, 'price') else item_obj.get('price', 0.0)
            item_cost = getattr(item_obj, 'cost', item_obj.get('cost', 0.0)) if hasattr(item_obj, 'cost') else item_obj.get('cost', 0.0)
            item_name = getattr(item_obj, 'name', item_obj.get('name', 'Unknown')) if hasattr(item_obj, 'name') else item_obj.get('name', 'Unknown')
            item_sku = getattr(item_obj, 'sku', item_obj.get('sku', 'Unknown')) if hasattr(item_obj, 'sku') else item_obj.get('sku', 'Unknown')
            
            if total_market_value > 0:
                weight = float(item_price) / total_market_value
                apportioned_sale_price = final_sale_price * weight
            else:
                apportioned_sale_price = 0.0
                
            profit = apportioned_sale_price - float(item_cost)
            
            db_item = db_session.query(InventoryItem).filter_by(sku=item_sku).first()
            if db_item and db_item.stock > 0:
                db_item.stock -= 1
                
            # Fee Tracking
            processing_fees = 0.0
            trade_credit_deduction = 0.0
            net_revenue = 0.0
            
            if payment_method.lower() == 'cash':
                net_revenue = apportioned_sale_price
            elif payment_method.lower() == 'trade credit':
                trade_credit_deduction = apportioned_sale_price
            elif payment_method.lower() == 'credit card':
                processing_fees = (apportioned_sale_price * 0.026) + 0.10
                net_revenue = apportioned_sale_price - processing_fees
                
            sale_record = Sale(
                item_name=item_name,
                sku=item_sku,
                sold_price=round(apportioned_sale_price, 2),
                profit=round(profit, 2),
                transaction_type=f"Sale - {payment_method}",
                processing_fees=round(processing_fees, 2),
                trade_credit_deduction=round(trade_credit_deduction, 2),
                net_revenue=round(net_revenue, 2)
            )
            db_session.add(sale_record)
            
        db_session.commit()
        return True, "Sale Finalized"
    except Exception as e:
        db_session.rollback()
        print(f"Error finalizing sale: {e}")
        return False, f"System Error: {str(e)}"
