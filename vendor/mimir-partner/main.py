import os
import sys
from log_capture import setup_logger
setup_logger(is_main_process=True)

# Get the directory where the script is running
if getattr(sys, 'frozen', False):
    # If running as an .exe (if you ever do build one)
    application_path = os.path.dirname(sys.executable)
elif __file__:
    # If running as a normal .py script
    application_path = os.path.dirname(os.path.abspath(__file__))

# Now always use application_path to find your files
db_path = os.path.join(application_path, "card_shop.db")
env_path = os.path.join(application_path, ".env")

import time
import threading
import queue
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
import json
import shutil
import pyperclip
import tkinter as tk
from PIL import Image, ImageTk
from sqlalchemy import func, case
from datetime import datetime, timedelta, timezone

from database import db_session, InventoryItem, Sale, StagingItem, PrintQueue, SystemSettings, PurchaseRecord, PendingTrade, ShowPriceCapture, ShowPriceCaptureItem, init_db, DB_PATH
from migrate_db import migrate
from logic import (calculate_net_profit, calculate_partial_trade, reconcile_databases,
                   process_captured_data, confirm_intake, generate_item_barcode,
                   print_barcode_to_label_printer, calculate_suggested_price, copy_text_to_clipboard, calculate_buy_cost, parse_collectr_csv,
                   run_reconciliation_audit, remove_signature_from_cache, clear_signatures_cache,
                   copy_barcode_to_clipboard, add_item_to_staging,
                   start_background_worker, manual_api_refetch, apply_trade_values_to_staging)
from core import CoreManager, PokemonTCGAPIClient, SQLAlchemyDatabaseClient
from services.gmail_monitor import get_gmail_monitor

APP_FONT_FAMILY = "Montserrat"
APP_FONT = (APP_FONT_FAMILY, 14)
APP_FONT_BOLD_LG = (APP_FONT_FAMILY, 20, "bold")
APP_FONT_SM = (APP_FONT_FAMILY, 11, "bold")
APP_FONT_TITLE = (APP_FONT_FAMILY, 32, "bold")


core_manager = CoreManager(
    db_client=SQLAlchemyDatabaseClient(),
    ocr_client=None,   # OCR pipeline removed — CoreManager still manages Shopify sync outbox
    api_client=PokemonTCGAPIClient()
)


class Cart:
    """
    Cart object that stores InventoryItem IDs.
    Provides a clean interface for accessing objects and calculating lot-sale metrics.
    """
    def __init__(self):
        self._item_ids = []

    def add(self, item_id):
        self._item_ids.append(item_id)

    def remove(self, index):
        if 0 <= index < len(self._item_ids):
            self._item_ids.pop(index)

    def clear(self):
        self._item_ids = []

    @property
    def items(self):
        return [it for iid in self._item_ids if (it := db_session.get(InventoryItem, iid))]

    @property
    def total_market_value(self):
        return sum(it.price for it in self.items)

class OverlayLayer(ctk.CTkFrame):
    """A full-screen internal overlay that mimics mobile view-stacking."""
    def __init__(self, master, title="OVERLAY VIEW", on_close=None):
        super().__init__(master, fg_color="#121212", corner_radius=0)
        self.on_close_callback = on_close
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with Close Button
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=60, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=25)
        
        ctk.CTkButton(header, text="✕ CLOSE", width=80, height=32, fg_color="#944747", hover_color="#7A3A3A",
                      command=self.close).pack(side="right", padx=25)

        # Content Container
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

    def close(self):
        if self.on_close_callback: self.on_close_callback()
        self.destroy()

class InventoryItemDetailView(ctk.CTkFrame):
    """Internal view for card details, replaces the old popup modal."""
    def __init__(self, master, item, close_callback):
        super().__init__(master, fg_color="transparent")
        self.item = item
        self.close_callback = close_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main Scrollable Container
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.grid(row=0, column=0, sticky="nsew")
        self.main_scroll.grid_columnconfigure(0, weight=1)

        # Large Artwork Header
        thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
        if os.path.exists(thumb_path):
            img = Image.open(thumb_path)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(240, 336))
            ctk_img_lbl = ctk.CTkLabel(self.main_scroll, image=ctk_img, text="")
            ctk_img_lbl.image = ctk_img
            ctk_img_lbl.pack(pady=20)

        # QR Code Display
        self.qr_frame = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.qr_frame.pack(pady=10)
        self.barcode_path = os.path.join(os.path.dirname(__file__), 'static', 'barcodes', f"{item.sku}.png")
        self._render_qr()

        # SKU Warning
        sku_warning_frame = ctk.CTkFrame(self.main_scroll, fg_color="#331111", border_color="#ff4444", border_width=1)
        sku_warning_frame.pack(fill="x", padx=30, pady=10)
        ctk.CTkLabel(sku_warning_frame, text="WARNING: Changing the SKU will migrate all history. If it matches an existing SKU, it will MERGE stock.", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffaaaa").pack(pady=10)

        # Parameters
        f = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        f.pack(fill="x", padx=30, pady=10)
        f.grid_columnconfigure(1, weight=1)

        self.entries = {}
        fields = [
            ("sku", "Card SKU:", item.sku),
            ("name", "Card Name:", item.name),
            ("set_name", "Set Name:", item.set_name),
            ("sequence_number", "Set Number:", item.sequence_number),
            ("price", "Market Price ($):", item.price),
            ("variant", "Variant:", item.variant),
            ("card_type", "Card Type:", item.card_type),
            ("condition", "Condition:", item.condition),
            ("stock", "Current Stock:", item.stock)
        ]

        for i, (key, label, val) in enumerate(fields):
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(weight="bold")).grid(row=i, column=0, sticky="w", padx=10, pady=6)
            entry = ctk.CTkEntry(f, height=35, border_color="#333333")
            entry.insert(0, str(val) if val is not None else "")
            entry.grid(row=i, column=1, sticky="ew", padx=10, pady=6)
            self.entries[key] = entry

        # Save Button
        ctk.CTkButton(self.main_scroll, text="💾 Save Card Data", command=self.save_changes, 
                      height=50, fg_color="#2fa572", font=ctk.CTkFont(weight="bold")).pack(pady=30, padx=30, fill="x")

        # Purchase Ledger
        hist_f = ctk.CTkFrame(self.main_scroll, fg_color="#1A1A1A", border_color="#2D2D2D", border_width=1)
        hist_f.pack(fill="x", padx=30, pady=20)
        ctk.CTkLabel(hist_f, text="📜 UNIT PURCHASE HISTORY", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        records = db_session.query(PurchaseRecord).filter_by(sku=item.sku).order_by(PurchaseRecord.timestamp.desc()).all()
        for r in records:
            row = ctk.CTkFrame(hist_f, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=10)
            date_str = r.timestamp.strftime("%Y-%m-%d")
            ctk.CTkLabel(row, text=f"{date_str}", width=100, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"Qty: {r.quantity}", width=60).pack(side="left")
            ctk.CTkLabel(row, text=f"@ ${r.cost_per_unit:.2f}/ea", text_color="#3b8ed0", font=ctk.CTkFont(weight="bold")).pack(side="right")

    def save_changes(self):
        try:
            old_price = self.item.price
            new_price = float(self.entries["price"].get().replace('$', ''))
            
            new_sku = self.entries["sku"].get().strip()
            if new_sku and new_sku != self.item.sku:
                from database import PurchaseRecord, SyncOutbox, PrintQueue, OnlinePullQueue, Sale, ShowPriceCaptureItem
                existing_item = db_session.query(InventoryItem).filter_by(sku=new_sku).first()
                old_sku = self.item.sku
                if existing_item:
                    existing_item.stock += int(self.entries["stock"].get())
                    db_session.query(PurchaseRecord).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(SyncOutbox).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(PrintQueue).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(OnlinePullQueue).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(Sale).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(ShowPriceCaptureItem).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.delete(self.item)
                    db_session.commit()
                    messagebox.showinfo("Merged", f"Item successfully merged into existing SKU: {new_sku}")
                    self.close_callback()
                    return
                else:
                    db_session.query(PurchaseRecord).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(SyncOutbox).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(PrintQueue).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(OnlinePullQueue).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(Sale).filter_by(sku=old_sku).update({"sku": new_sku})
                    db_session.query(ShowPriceCaptureItem).filter_by(sku=old_sku).update({"sku": new_sku})
                    self.item.sku = new_sku

            self.item.name = self.entries["name"].get()
            self.item.set_name = self.entries["set_name"].get()
            self.item.sequence_number = self.entries["sequence_number"].get()
            self.item.price = new_price
            self.item.variant = self.entries["variant"].get()
            self.item.card_type = self.entries["card_type"].get()
            self.item.condition = self.entries["condition"].get()
            self.item.stock = int(self.entries["stock"].get())
            
            if abs(old_price - new_price) > 0.001:
                from database import SyncOutbox, SystemSettings
                from logic import calculate_shop_listing_price, calculate_suggested_price
                settings = db_session.query(SystemSettings).first()
                rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
                shop_price = calculate_shop_listing_price(new_price, self.item.card_type)
                
                self.item.sticker_price = calculate_suggested_price(new_price, rule=rounding_rule)
                self.item.shop_listing_price = shop_price
                outbox = SyncOutbox(action_type='price_update', sku=self.item.sku, quantity_change=0, new_price=shop_price)
                db_session.add(outbox)
                
            db_session.commit()
            messagebox.showinfo("Success", "Card updated.")
            self.close_callback()
        except Exception as e:
            db_session.rollback()
            messagebox.showerror("Error", str(e))

    def _render_qr(self):
        for widget in self.qr_frame.winfo_children():
            widget.destroy()
            
        if os.path.exists(self.barcode_path):
            try:
                img = Image.open(self.barcode_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 75))
                lbl = ctk.CTkLabel(self.qr_frame, image=ctk_img, text="")
                lbl.image = ctk_img
                lbl.pack()
                
                btn_frame = ctk.CTkFrame(self.qr_frame, fg_color="transparent")
                btn_frame.pack(pady=5)
                
                def do_copy(format_type):
                    from logic import generate_item_barcode, copy_barcode_to_clipboard
                    generate_item_barcode(self.item.sku, market_price=self.item.price, format=format_type)
                    success = copy_barcode_to_clipboard(self.item.sku)
                    if success:
                        pass # messagebox can be intrusive here, keeping it silent/minimal
                    else:
                        messagebox.showerror("Error", "Failed to copy.")
                        
                ctk.CTkButton(btn_frame, text="Copy Barcode", command=lambda: do_copy("Barcode"), width=100, fg_color="#444444").pack(side="left", padx=5)
                ctk.CTkButton(btn_frame, text="Copy QR", command=lambda: do_copy("QR"), width=100, fg_color="#3b8ed0").pack(side="left", padx=5)
            except Exception as e:
                ctk.CTkLabel(self.qr_frame, text=f"Error loading QR: {e}").pack()
        else:
            ctk.CTkButton(self.qr_frame, text="Generate QR Code", fg_color="#3b8ed0", command=self._generate_qr).pack()
            
    def _generate_qr(self):
        from logic import generate_item_barcode
        generate_item_barcode(self.item.sku, market_price=self.item.price, format="QR")
        self._render_qr()

class HistoryCatalogView(ctk.CTkFrame):
    """Internal view for the master card catalog."""
    def __init__(self, master, on_select_callback, close_callback):
        super().__init__(master, fg_color="transparent")
        self.on_select_callback = on_select_callback
        self.close_callback = close_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Search Bar
        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search all unique cards ever entered...", height=45, border_color="#333333")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_list())
        
        self.scroll = ctk.CTkScrollableFrame(self, label_text="MASTER UNIQUE CARD LIST")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.scroll.grid_columnconfigure(1, weight=1)
        
        self.refresh_list()

    def refresh_list(self):
        for child in self.scroll.winfo_children(): child.destroy()
        query = self.search_entry.get().lower()
        items = db_session.query(InventoryItem).filter(
            (InventoryItem.name.ilike(f"%{query}%")) | (InventoryItem.sku.ilike(f"%{query}%"))
        ).group_by(InventoryItem.sku).all()

        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="#1A1A1A", border_width=1, border_color="#2D2D2D")
            row.pack(fill="x", pady=4, padx=5)
            
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
            if os.path.exists(thumb_path):
                img = Image.open(thumb_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 56))
                ctk_img_lbl = ctk.CTkLabel(row, image=ctk_img, text="")
                ctk_img_lbl.image = ctk_img
                ctk_img_lbl.pack(side="left", padx=10, pady=5)
            
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", padx=10, fill="y")
            ctk.CTkLabel(info, text=item.name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=f"{item.set_name} | {item.sku}", text_color="#8E8E8E", font=("Arial", 10)).pack(anchor="w")
            
            ctk.CTkButton(row, text="+ Add to Staging", width=140, height=32, fg_color="#3b8ed0",
                          command=lambda i=item: self.select_item(i)).pack(side="right", padx=15)

    def select_item(self, item):
        data = {
            "name": item.name, "set_name": item.set_name, "sequence_number": item.sequence_number,
            "variant": item.variant, "condition": item.condition, "card_type": item.card_type,
            "market_price": item.price, "quantity": 1, "sku": item.sku,
            "image_path": os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
        }
        add_item_to_staging(data)
        self.on_select_callback()
        self.close_callback()

class ReconciliationFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        self.volatility_data = []
        self.grid_columnconfigure((0,1,2), weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkButton(self, text="Load Collectr Export (.csv)", command=self.load_csv, fg_color="#3b8ed0").grid(row=0, column=0, pady=10, padx=10, sticky="w")
        self.apply_btn = ctk.CTkButton(self, text="🔄 Bulk Apply Price Adjustments", state="disabled", command=self.bulk_apply, fg_color="#2fa572")
        self.apply_btn.grid(row=0, column=2, pady=10, padx=10, sticky="e")

        self.rem_list = ctk.CTkScrollableFrame(self, label_text="REMOVAL LIST (SOLD)")
        self.rem_list.grid(row=1, column=0, sticky="nsew", padx=5)
        self.in_list = ctk.CTkScrollableFrame(self, label_text="INTAKE LIST (PENDING)")
        self.in_list.grid(row=1, column=1, sticky="nsew", padx=5)
        self.vol_list = ctk.CTkScrollableFrame(self, label_text="PRICE VOLATILITY DASHBOARD")
        self.vol_list.grid(row=1, column=2, sticky="nsew", padx=5)

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not path: return
        csv_data = parse_collectr_csv(path)
        rem, intake, vol = run_reconciliation_audit(csv_data)
        self.volatility_data = vol
        self.render_lists(rem, intake, vol)
        if vol: self.apply_btn.configure(state="normal")

    def render_lists(self, rem, intake, vol):
        import sys, os
        img_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image_db_manager')
        if img_db_path not in sys.path:
            sys.path.append(img_db_path)
        try:
            import db_handler as img_db_handler
        except ImportError:
            img_db_handler = None

        for f in [self.rem_list, self.in_list, self.vol_list]:
            for child in f.winfo_children(): child.destroy()
            
        def _add_image_to_row(row_frame, name, set_name, seq):
            if not img_db_handler: return
            local_img = img_db_handler.find_image_by_set_and_number(set_name, seq, card_name=name)
            if local_img and os.path.exists(local_img):
                try:
                    img = Image.open(local_img)
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 42))
                    ctk_img_lbl = ctk.CTkLabel(row_frame, image=ctk_img, text="")
                    ctk_img_lbl.image = ctk_img
                    ctk_img_lbl.pack(side="left", padx=(0, 5))
                except Exception:
                    pass
                        
        for r in rem:
            row = ctk.CTkFrame(self.rem_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            _add_image_to_row(row, r.get('name'), r.get('set_name'), r.get('sequence_number'))
            ctk.CTkLabel(row, text=f"{r['name']} (-{r['qty_to_remove']})", anchor="w").pack(side="left")
            
            def make_reconcile_cmd(sku, qty, r_frame, skus=None):
                def cmd():
                    from database import db_session, Sale
                    sku_list = skus if skus else [sku]
                    sales = db_session.query(Sale).filter(Sale.sku.in_(sku_list), Sale.is_reconciled==False).order_by(Sale.timestamp.asc()).limit(qty).all()
                    for s in sales:
                        s.is_reconciled = True
                    db_session.commit()
                    r_frame.destroy()
                return cmd
                
            ctk.CTkButton(row, text="📋", width=30, command=lambda n=r['name']: copy_text_to_clipboard(n)).pack(side="right", padx=(5, 0))
            ctk.CTkButton(row, text="✔️ Mark Done", width=80, fg_color="#2fa572", hover_color="#238258", command=make_reconcile_cmd(r['sku'], r['qty_to_remove'], row, r.get('skus'))).pack(side="right", padx=(5, 0))
            
        for i in intake:
            row = ctk.CTkFrame(self.in_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            _add_image_to_row(row, i.get('name'), i.get('set_name'), i.get('sequence_number'))
            ctk.CTkLabel(row, text=f"{i['name']} (+{i['qty_to_add']})", anchor="w").pack(side="left")
            
        for v in vol:
            row = ctk.CTkFrame(self.vol_list, fg_color="transparent")
            row.pack(fill="x", pady=5)
            set_name = v['items'][0].set_name if v.get('items') else v.get('set_name')
            _add_image_to_row(row, v.get('name'), set_name, v.get('sequence_number'))
            ctk.CTkLabel(row, text=f"{v['name']}\nCurrent Price: ${v['old_price']:.2f} -> New Price: ${v['suggested']:.2f} (Mkt: ${v['market_value']:.2f})", justify="left").pack(side="left")

    def bulk_apply(self):
        from database import db_session, SyncOutbox
        for entry in self.volatility_data:
            for it in entry['items']:
                it.price = entry['suggested']
                it.needs_update = False
                
                from database import SystemSettings
                from logic import calculate_shop_listing_price, calculate_suggested_price
                settings = db_session.query(SystemSettings).first()
                rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
                
                it.sticker_price = calculate_suggested_price(entry['suggested'], rule=rounding_rule)
                shop_price = calculate_shop_listing_price(entry['suggested'], it.card_type)
                it.shop_listing_price = shop_price
                
                # Push price update to SyncOutbox (Offline-First)
                outbox = SyncOutbox(
                    action_type='price_update', 
                    sku=it.sku, 
                    quantity_change=0, 
                    new_price=shop_price
                )
                db_session.add(outbox)
                
        db_session.commit()
        self.refresh_callback()
        messagebox.showinfo("Success", "Prices updated.")
        self.apply_btn.configure(state="disabled")

class PartialTradeView(ctk.CTkFrame):
    """Internal view for processing trades, formerly a modal."""
    def __init__(self, master, cart_items, on_commit_callback, close_callback):
        super().__init__(master, fg_color="transparent")
        self.on_commit_callback = on_commit_callback
        self.close_callback = close_callback
        self.cart_items = cart_items
        self.incoming_trades = []
        self.cash_tendered_var = tk.StringVar(value="")
        self.cash_tendered_var.trace_add("write", lambda *args: self.update_calculations())
        self.store_cash_var = tk.StringVar(value="")
        self.store_cash_var.trace_add("write", lambda *args: self.update_calculations())
        self.customer_cash_var = tk.StringVar(value="")
        self.customer_cash_var.trace_add("write", lambda *args: self.update_calculations())
        
        settings = db_session.query(SystemSettings).first()
        self.buy_rate = settings.buy_percentage if settings else 0.70
        self.trade_rate = settings.trade_percentage if settings else 0.80

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="TRADE & SETTLEMENT ENGINE", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=10)

        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, bd=0, sashwidth=8, bg="#1F1F23")
        self.paned_window.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # --- LEFT SIDE: Manual Intake ---
        self.manual_intake = ManualIntakeFrame(self.paned_window, add_callback=self.on_card_added)
        self.paned_window.add(self.manual_intake, minsize=320, stretch="always")

        # --- RIGHT SIDE: Trade Details ---
        self.right_container = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        self.right_container.grid_columnconfigure(0, weight=1)
        self.right_container.grid_rowconfigure(1, weight=1)

        # Cart Summary
        total_out = sum(i.price for i in cart_items)
        out_f = ctk.CTkFrame(self.right_container, fg_color="#1A1A1A")
        out_f.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(out_f, text=f"OUTGOING CART TOTAL: ${total_out:.2f}", font=ctk.CTkFont(weight="bold")).pack(pady=10)

        # Queue
        self.scroll = ctk.CTkScrollableFrame(self.right_container, label_text="CUSTOMER TRADE-IN QUEUE")
        self.scroll.grid(row=1, column=0, sticky="nsew", pady=10)
        
        # Results Frame
        res_f = ctk.CTkFrame(self.right_container, fg_color="transparent")
        res_f.grid(row=2, column=0, pady=15, sticky="ew")

        # Placeholder Trade button — appears above NET DUE
        ctk.CTkButton(res_f, text="💳 Add Placeholder Trade",
                      fg_color="#D97706", hover_color="#B45309",
                      font=ctk.CTkFont(weight="bold"), height=38,
                      command=self.add_placeholder_trade
                      ).pack(fill="x", pady=(0, 10))

        self.summary_lbl = ctk.CTkLabel(res_f, text="NET DUE: $0.00", font=ctk.CTkFont(size=22, weight="bold"), text_color="#2fa572")
        self.summary_lbl.pack(pady=(0, 10))
        
        cash_f = ctk.CTkFrame(res_f, fg_color="transparent")
        cash_f.pack()
        
        # Settle/Tender
        ctk.CTkLabel(cash_f, text="Cash Tendered: $").grid(row=0, column=0, padx=5, sticky="e")
        self.cash_entry = ctk.CTkEntry(cash_f, textvariable=self.cash_tendered_var, width=100, border_color="#333333")
        self.cash_entry.grid(row=0, column=1, padx=5, pady=2)
        
        # Cash on Top
        ctk.CTkLabel(cash_f, text="Store Cash Added: $").grid(row=1, column=0, padx=5, sticky="e")
        ctk.CTkEntry(cash_f, textvariable=self.store_cash_var, width=100, border_color="#333333").grid(row=1, column=1, padx=5, pady=2)
        
        ctk.CTkLabel(cash_f, text="Customer Cash Added: $").grid(row=2, column=0, padx=5, sticky="e")
        ctk.CTkEntry(cash_f, textvariable=self.customer_cash_var, width=100, border_color="#333333").grid(row=2, column=1, padx=5, pady=2)
        
        self.change_lbl = ctk.CTkLabel(res_f, text="Change Due: $0.00", font=ctk.CTkFont(size=18, weight="bold"), text_color="#EAB308")
        self.change_lbl.pack(pady=(10, 0))

        ctk.CTkButton(self.right_container, text="✅ FINALIZE TRANSACTION", command=self.process_commit, height=55, fg_color="#2fa572").grid(row=3, column=0, pady=10)

        self.paned_window.add(self.right_container, minsize=400, stretch="always")
        
        self.after(100, lambda: self.paned_window.sash_place(0, int(self.winfo_width() * 0.40), 0))
        self.update_calculations()


    def on_card_added(self, card_data=None):
        """Called when a card is scanned or manually submitted"""
        if not card_data: return
        self.incoming_trades.append({
            "name": card_data.get('name', 'Unknown'),
            "market_value": card_data.get('market_price', 0.0),
            "sequence_number": card_data.get('sequence_number', 'N/A'),
            "rate": self.trade_rate,
            "image_path": card_data.get('image_path'),
            "card_type": card_data.get('card_type', 'Manual'),
            "variant": card_data.get('variant', 'Manual'),
            "condition": card_data.get('condition', 'Manual'),
            "set_name": card_data.get('set_name', 'Trade')
        })
        self.after(0, self.refresh_list)

    def refresh_list(self):
        for child in self.scroll.winfo_children(): child.destroy()
        for idx, item in enumerate(self.incoming_trades):
            is_placeholder = (item.get('card_type') == 'Placeholder')
            bg_color = "#1A1200" if is_placeholder else "transparent"
            border_color = "#D97706" if is_placeholder else None
            border_width = 1 if is_placeholder else 0

            row = ctk.CTkFrame(self.scroll, fg_color=bg_color, border_color=border_color, border_width=border_width, corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)
            
            # Name and Price
            text_color = "#EAB308" if is_placeholder else "#FFFFFF"
            ctk.CTkLabel(row, text=f"{item['name']} ({item['sequence_number']})", anchor="w", text_color=text_color, font=ctk.CTkFont(weight="bold" if is_placeholder else "normal")).pack(side="left", padx=10, expand=True, fill="x")
            
            # Market Value Label
            mkt_val = item['market_value']
            ctk.CTkLabel(row, text=f"Mkt: ${mkt_val:.2f}", text_color="#EAB308" if is_placeholder else "#A1A1AA").pack(side="left", padx=5)
            
            # Rate Entry
            rate_var = tk.StringVar(value=str(int(item['rate'] * 100)))
            val_lbl = ctk.CTkLabel(row, text=f"${mkt_val * item['rate']:.2f}", text_color="#EAB308" if is_placeholder else "#3b8ed0", font=ctk.CTkFont(weight="bold"), width=60, anchor="e")
            
            def on_rate_change(*args, i=idx, v=rate_var, l=val_lbl, mv=mkt_val):
                try:
                    new_rate = float(v.get()) / 100.0
                    old_rate = self.incoming_trades[i].get('rate', 0.0)
                    self.incoming_trades[i]['rate'] = new_rate
                    new_val = mv * new_rate
                    l.configure(text=f"${new_val:.2f}")
                    # Update database PendingTrade in real time
                    pt_id = self.incoming_trades[i].get('pending_trade_id')
                    if pt_id:
                        try:
                            from database import db_session, PendingTrade
                            pt = db_session.query(PendingTrade).get(pt_id)
                            if pt:
                                old_val = mv * old_rate
                                pt.total_cash_paid = max(0.0, pt.total_cash_paid - old_val + new_val)
                                db_session.commit()
                        except:
                            db_session.rollback()
                    self.update_calculations()
                except ValueError:
                    pass
                    
            rate_var.trace_add("write", on_rate_change)
            
            ctk.CTkLabel(row, text="Rate %:", text_color="#EAB308" if is_placeholder else "#FFFFFF").pack(side="left", padx=(10, 2))
            ctk.CTkEntry(row, textvariable=rate_var, width=40, height=24, border_color="#D97706" if is_placeholder else "#333333", text_color="#EAB308" if is_placeholder else "#FFFFFF").pack(side="left", padx=2)
            
            # Value Label
            val_lbl.pack(side="left", padx=10)
            
            ctk.CTkButton(row, text="✕", width=25, height=25, fg_color="#944747", command=lambda i=idx: self.remove_item(i)).pack(side="right", padx=5)
        self.update_calculations()

    def remove_item(self, idx):
        item = self.incoming_trades.pop(idx)
        pt_id = item.get('pending_trade_id')
        if pt_id:
            try:
                from database import db_session, PendingTrade
                pt = db_session.query(PendingTrade).get(pt_id)
                if pt:
                    val = item['market_value'] * item.get('rate', self.trade_rate)
                    pt.total_market_value = max(0.0, pt.total_market_value - item['market_value'])
                    pt.total_cash_paid = max(0.0, pt.total_cash_paid - val)
                    if pt.total_market_value == 0 and pt.total_cash_paid == 0:
                        db_session.delete(pt)
                    db_session.commit()
            except Exception as e:
                db_session.rollback()
                print(f"[PartialTradeView] Error removing trade: {e}")
        self.refresh_list()

    def add_placeholder_trade(self):
        """Open the shared dialog and record a PendingTrade into the trade queue."""
        dlg = PlaceholderTradeDialog(self.winfo_toplevel(), self.trade_rate)
        self.winfo_toplevel().wait_window(dlg)
        if dlg.result:
            mkt_val, cash_paid = dlg.result
            try:
                from database import db_session, PendingTrade
                trade = db_session.query(PendingTrade).filter_by(status='pending').first()
                if trade:
                    trade.total_market_value += mkt_val
                    trade.total_cash_paid += cash_paid
                else:
                    trade = PendingTrade(total_market_value=mkt_val, total_cash_paid=cash_paid)
                    db_session.add(trade)
                db_session.commit()
                trade_id = trade.id
            except Exception as e:
                db_session.rollback()
                print(f"[PartialTradeView] PendingTrade save error: {e}")
                trade_id = None

            rate = cash_paid / mkt_val if mkt_val > 0 else self.trade_rate
            self.incoming_trades.append({
                "name": "Placeholder Trade",
                "market_value": mkt_val,
                "sequence_number": f"PT-{trade_id or 'NEW'}",
                "rate": rate,
                "image_path": None,
                "card_type": "Placeholder",
                "variant": "Placeholder",
                "condition": "Placeholder",
                "set_name": "Placeholder",
                "pending_trade_id": trade_id
            })
            self.refresh_list()

    def update_calculations(self):
        total_out = sum(i.price for i in self.cart_items)
        total_credit = sum(i['market_value'] * i['rate'] for i in self.incoming_trades)
        
        try: store_cash = float(self.store_cash_var.get()) if self.store_cash_var.get() else 0.0
        except ValueError: store_cash = 0.0
        try: cust_cash = float(self.customer_cash_var.get()) if self.customer_cash_var.get() else 0.0
        except ValueError: cust_cash = 0.0
        
        net = total_out - total_credit + store_cash - cust_cash
        self.summary_lbl.configure(text=f"NET DUE: ${net:.2f}", text_color="#2fa572" if net >= 0 else "#944747")
        
        try:
            tendered = float(self.cash_tendered_var.get()) if self.cash_tendered_var.get() else 0.0
        except ValueError:
            tendered = 0.0
            
        if net > 0 and tendered > 0:
            change = tendered - net
            self.change_lbl.configure(text=f"Change Due: ${change:.2f}")
        else:
            self.change_lbl.configure(text="Change Due: $0.00")

    def process_commit(self):
        try:
            from database import db_session, Sale, SyncOutbox
            total_credit = sum(i['market_value'] * i['rate'] for i in self.incoming_trades)
            total_market = sum(i['market_value'] for i in self.incoming_trades if i.get('card_type') != 'Placeholder')
            
            try: store_cash = float(self.store_cash_var.get()) if self.store_cash_var.get() else 0.0
            except ValueError: store_cash = 0.0
            try: cust_cash = float(self.customer_cash_var.get()) if self.customer_cash_var.get() else 0.0
            except ValueError: cust_cash = 0.0
            
            try:
                tendered = float(self.cash_tendered_var.get()) if self.cash_tendered_var.get() else 0.0
            except ValueError:
                tendered = 0.0
                
            transaction_type = "Checkout/Settlement"
            if tendered > 0 and total_credit == 0:
                transaction_type = "Cash Sale"
            elif total_credit > 0 and tendered == 0 and store_cash == 0 and cust_cash == 0:
                transaction_type = "Pure Trade"
            
            for item in self.cart_items:
                item.stock -= 1
                db_session.add(Sale(item_name=item.name, sku=item.sku, sold_price=item.price, profit=item.price - item.cost, transaction_type=transaction_type, trade_in_value=total_credit))
                
                # Enqueue inventory deduction for Shopify
                outbox = SyncOutbox(action_type='sale', sku=item.sku, quantity_change=-1, new_price=0.0)
                db_session.add(outbox)
                
            for tin in self.incoming_trades:
                if tin.get('card_type') == 'Placeholder':
                    continue
                from database import InventoryItem, PurchaseRecord
                import os
                import shutil
                
                base_cost = tin.get('market_value', 0.0) * tin.get('rate', self.trade_rate)
                if total_market > 0:
                    weight = tin.get('market_value', 0.0) / total_market
                    adjusted_cost = base_cost + (store_cash * weight) - (cust_cash * weight)
                else:
                    adjusted_cost = base_cost
                final_cost = max(0.0, adjusted_cost)
                
                # Check for existing inventory to merge SKU
                existing_item = db_session.query(InventoryItem).filter(
                    InventoryItem.name == tin.get('name', 'Unknown'),
                    InventoryItem.set_name == tin.get('set_name', 'Trade'),
                    InventoryItem.sequence_number == tin.get('sequence_number', ''),
                    InventoryItem.variant == tin.get('variant', 'Normal'),
                    InventoryItem.condition == tin.get('condition', 'Near Mint')
                ).first()
                
                if existing_item:
                    # Merge into existing item
                    total_qty = existing_item.stock + 1
                    if total_qty > 0:
                        new_avg_cost = ((existing_item.cost * existing_item.stock) + final_cost) / total_qty
                        existing_item.cost = round(new_avg_cost, 2)
                    existing_item.stock = total_qty
                    existing_item.needs_update = True
                    existing_item.sync_status = 'paused'
                    
                    db_session.add(PurchaseRecord(sku=existing_item.sku, quantity=1, cost_per_unit=final_cost))
                    
                    # Update thumbnail if one exists
                    img_path = tin.get('image_path')
                    if img_path and os.path.exists(img_path):
                        new_thumb = os.path.join('static', 'scraped_thumbnails', f"{existing_item.sku}.png")
                        os.makedirs(os.path.dirname(new_thumb), exist_ok=True)
                        shutil.copy(img_path, new_thumb)
                        existing_item.image_url = new_thumb
                else:
                    # Create completely new item
                    sku = f"CS-{os.urandom(2).hex().upper()}"
                    
                    new_img_url = ""
                    img_path = tin.get('image_path')
                    if img_path and os.path.exists(img_path):
                        new_thumb = os.path.join('static', 'scraped_thumbnails', f"{sku}.png")
                        os.makedirs(os.path.dirname(new_thumb), exist_ok=True)
                        shutil.copy(img_path, new_thumb)
                        new_img_url = new_thumb
                        
                    new_item = InventoryItem(
                        sku=sku,
                        name=tin.get('name', 'Unknown'),
                        set_name=tin.get('set_name', 'Trade'),
                        sequence_number=tin.get('sequence_number', ''),
                        price=tin.get('market_value', 0.0),
                        cost=final_cost,
                        stock=1,
                        card_type=tin.get('card_type', 'Single'),
                        variant=tin.get('variant', 'Normal'),
                        condition=tin.get('condition', 'Near Mint'),
                        image_url=new_img_url,
                        sync_status='paused',
                        needs_update=True
                    )
                    db_session.add(new_item)
                    db_session.add(PurchaseRecord(sku=sku, quantity=1, cost_per_unit=final_cost))
            db_session.commit()
            
            # Delayed background trigger to process the outbox so Shopify gets the deductions
            def _delayed_sync():
                import time
                time.sleep(5)
                if core_manager:
                    core_manager._process_sync_outbox()
            import threading
            threading.Thread(target=_delayed_sync, daemon=True).start()
            
            self.on_commit_callback(); self.close_callback()
        except Exception as e:
            print(f"Error commiting trade: {e}")
            db_session.rollback()

class StraightBuyView(ctk.CTkFrame):
    """Internal view for processing a single buy-in."""
    def __init__(self, master, on_commit_callback, close_callback):
        super().__init__(master, fg_color="transparent")
        self.on_commit_callback = on_commit_callback
        self.close_callback = close_callback
        
        settings = db_session.query(SystemSettings).first()
        self.buy_rate = settings.buy_percentage if settings else 0.70
        self.trade_rate = settings.trade_percentage if settings else 0.80

        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="STRAIGHT BUY-IN ENGINE", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=30)

        # Inputs
        self.in_name = ctk.CTkEntry(self, placeholder_text="Card Name", width=400, height=45, border_color="#333333")
        self.in_name.pack(pady=10)
        self.in_set = ctk.CTkEntry(self, placeholder_text="Set Number", width=400, height=45, border_color="#333333")
        self.in_set.pack(pady=10)
        self.in_market = ctk.CTkEntry(self, placeholder_text="Market Value ($)", width=400, height=45, border_color="#333333")
        self.in_market.pack(pady=10)
        self.in_market.bind("<KeyRelease>", lambda e: self.update_payout())

        # Method
        self.method_var = tk.StringVar(value="cash")
        m_f = ctk.CTkFrame(self, fg_color="transparent")
        m_f.pack(pady=20)
        ctk.CTkRadioButton(m_f, text="Cash Payout", variable=self.method_var, value="cash", command=self.update_payout).pack(side="left", padx=20)
        ctk.CTkRadioButton(m_f, text="Store Credit", variable=self.method_var, value="trade", command=self.update_payout).pack(side="left", padx=20)

        self.payout_lbl = ctk.CTkLabel(self, text="TOTAL PAYOUT: $0.00", font=ctk.CTkFont(size=24, weight="bold"), text_color="#3b8ed0")
        self.payout_lbl.pack(pady=30)

        ctk.CTkButton(self, text="✅ PROCESS & STAGE BUY-IN", command=self.process_buy, height=60, width=400, fg_color="#2fa572").pack(pady=10)

    def update_payout(self):
        try:
            val = float(self.in_market.get()) if self.in_market.get() else 0.0
            rate = self.buy_rate if self.method_var.get() == "cash" else self.trade_rate
            self.payout_lbl.configure(text=f"TOTAL PAYOUT: ${val * rate:.2f}")
        except: pass

    def process_buy(self):
        try:
            m_val = float(self.in_market.get())
            name = self.in_name.get().strip()
            if not name: raise ValueError
            
            rate = self.buy_rate if self.method_var.get() == "cash" else self.trade_rate
            payout = round(m_val * rate, 2)
            intake_data = confirm_intake({"name": name, "sequence_number": self.in_set.get(), "market_value": m_val})
            
            staging_data = {
                "name": intake_data['name'], "set_name": intake_data['set_name'], "sequence_number": intake_data['sequence_number'],
                "market_price": m_val, "cost_basis": payout, "quantity": 1, "sku": intake_data['sku'],
                "card_type": intake_data.get('card_type', 'Manual'), "variant": intake_data.get('variant', 'Manual'), "condition": intake_data.get('condition', 'Manual')
            }
            add_item_to_staging(staging_data)
            
            db_session.add(Sale(item_name=f"BUY-IN: {name}", sku=intake_data['sku'], sold_price=0, profit=-payout, transaction_type="Buy-In", trade_in_value=payout))
            db_session.commit()
            self.on_commit_callback()
            self.close_callback()
        except: messagebox.showerror("Error", "Check name and numeric values.")

class BulkBuyView(ctk.CTkFrame):
    """Internal view for batch buy-ins."""
    def __init__(self, master, on_commit_callback, close_callback):
        super().__init__(master, fg_color="transparent")
        self.on_commit_callback = on_commit_callback
        self.close_callback = close_callback
        self.items_to_buy = []
        
        settings = db_session.query(SystemSettings).first()
        self.buy_rate = settings.buy_percentage if settings else 0.70
        self.trade_rate = settings.trade_percentage if settings else 0.80

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="BULK BUY-IN WORKSPACE", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=20)

        # Input Row
        in_f = ctk.CTkFrame(self, fg_color="#1A1A1A", border_width=1, border_color="#2D2D2D")
        in_f.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        in_f.grid_columnconfigure(0, weight=1)
        
        self.in_name = ctk.CTkEntry(in_f, placeholder_text="Card Name", height=40, border_color="#333333")
        self.in_name.grid(row=0, column=0, padx=10, pady=15, sticky="ew")
        self.in_set = ctk.CTkEntry(in_f, placeholder_text="Set #", width=120, height=40, border_color="#333333")
        self.in_set.grid(row=0, column=1, padx=5, pady=15)
        self.in_mkt = ctk.CTkEntry(in_f, placeholder_text="Market $", width=120, height=40, border_color="#333333")
        self.in_mkt.grid(row=0, column=2, padx=5, pady=15)
        self.in_mkt.bind("<Return>", lambda e: self.add_item())
        ctk.CTkButton(in_f, text="+ ADD", width=80, height=40, command=self.add_item).grid(row=0, column=3, padx=10, pady=15)

        # List
        self.scroll = ctk.CTkScrollableFrame(self, label_text="QUEUED BATCH ITEMS")
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        
        # Footer
        footer = ctk.CTkFrame(self, fg_color="#1A1A1A")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=20)
        
        self.method_var = tk.StringVar(value="cash")
        ctk.CTkRadioButton(footer, text="Cash", variable=self.method_var, value="cash", command=self.update_summary).pack(side="left", padx=20)
        ctk.CTkRadioButton(footer, text="Credit", variable=self.method_var, value="trade", command=self.update_summary).pack(side="left", padx=20)
        
        self.summary_lbl = ctk.CTkLabel(footer, text="Payout: $0.00", font=ctk.CTkFont(size=18, weight="bold"))
        self.summary_lbl.pack(side="right", padx=30)

        ctk.CTkButton(self, text="🚀 FINALIZE BULK TRANSACTION", command=self.process_bulk, height=50, fg_color="#2fa572").grid(row=4, column=0, pady=(0, 20))

    def add_item(self):
        try:
            m = float(self.in_mkt.get())
            n = self.in_name.get().strip()
            if not n: return
            self.items_to_buy.append({"name": n, "sequence_number": self.in_set.get() or "N/A", "market_value": m})
            self.in_name.delete(0, tk.END); self.in_set.delete(0, tk.END); self.in_mkt.delete(0, tk.END); self.in_name.focus()
            self.refresh_list(); self.update_summary()
        except: pass

    def refresh_list(self):
        for child in self.scroll.winfo_children(): child.destroy()
        for idx, item in enumerate(self.items_to_buy):
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{item['name']} ({item['sequence_number']})", anchor="w").pack(side="left", padx=10, expand=True, fill="x")
            ctk.CTkLabel(row, text=f"${item['market_value']:.2f}", width=80).pack(side="left")
            ctk.CTkButton(row, text="✕", width=25, height=25, fg_color="#944747", command=lambda i=idx: self.remove_item(i)).pack(side="right", padx=5)

    def remove_item(self, idx):
        self.items_to_buy.pop(idx); self.refresh_list(); self.update_summary()

    def update_summary(self):
        total = sum(i['market_value'] for i in self.items_to_buy)
        rate = self.buy_rate if self.method_var.get() == "cash" else self.trade_rate
        self.summary_lbl.configure(text=f"Total Payout: ${total * rate:.2f}")

    def process_bulk(self):
        if not self.items_to_buy: return
        rate = self.buy_rate if self.method_var.get() == "cash" else self.trade_rate
        try:
            for item in self.items_to_buy:
                p = round(item['market_value'] * rate, 2)
                intake = confirm_intake(item)
                add_item_to_staging({"name": intake['name'], "set_name": intake.get('set_name', 'Bulk'), "sequence_number": intake['sequence_number'],
                                    "market_price": item['market_value'], "cost_basis": p, "quantity": 1, "sku": intake['sku'],
                                    "card_type": intake.get('card_type', 'Manual'), "variant": intake.get('variant', 'Manual'), "condition": intake.get('condition', 'Manual')})
                db_session.add(Sale(item_name=f"BULK: {intake['name']}", sku=intake['sku'], sold_price=0, profit=-p, transaction_type="Bulk Buy", trade_in_value=p))
            db_session.commit()
            self.on_commit_callback(); self.close_callback()
        except: db_session.rollback()


class PlaceholderTradeDialog(ctk.CTkToplevel):
    """
    Shared dialog for adding a placeholder trade to any checkout flow.
    Records a PendingTrade with total_market_value and total_cash_paid.
    result = (market_value: float, cash_paid: float) or None if cancelled.
    """
    def __init__(self, master, default_buy_rate=0.70):
        super().__init__(master)
        self.title("Add Placeholder Trade")
        self.geometry("420x340")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result = None
        self._default_rate = default_buy_rate

        self._mkt_var = tk.StringVar()
        self._buy_pct_var = tk.StringVar(value=str(int(default_buy_rate * 100)))
        self._flat_var = tk.StringVar(value="0.00")

        self._build_ui()
        self.after(100, self._mkt_entry.focus_set)

    def _parse_val(self, s):
        if not s:
            return 0.0
        clean = s.replace('$', '').replace('%', '').replace(',', '').strip()
        try:
            return float(clean)
        except ValueError:
            return 0.0

    def _build_ui(self):
        self.configure(fg_color="#121212")
        pad = {"padx": 20, "pady": 8}

        ctk.CTkLabel(self, text="💳 ADD PLACEHOLDER TRADE",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#D97706").pack(**pad)

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", **pad)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Trade Market Value ($):", anchor="w").grid(row=0, column=0, sticky="w", pady=10)
        self._mkt_entry = ctk.CTkEntry(f, textvariable=self._mkt_var, width=180, border_color="#333333")
        self._mkt_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=10)
        self._mkt_entry.bind("<KeyRelease>", self._on_mkt_change)

        ctk.CTkLabel(f, text="Trade % (e.g. 80):", anchor="w").grid(row=1, column=0, sticky="w", pady=10)
        self._pct_entry = ctk.CTkEntry(f, textvariable=self._buy_pct_var, width=180, border_color="#333333")
        self._pct_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=10)
        self._pct_entry.bind("<KeyRelease>", self._on_pct_change)

        ctk.CTkLabel(f, text="Trade Cash Amount ($):", anchor="w").grid(row=2, column=0, sticky="w", pady=10)
        self._flat_entry = ctk.CTkEntry(f, textvariable=self._flat_var, width=180, border_color="#333333")
        self._flat_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=10)
        self._flat_entry.bind("<KeyRelease>", self._on_flat_change)

        # Result preview
        self._result_lbl = ctk.CTkLabel(self, text="Cash to pay: $0.00",
                                         font=ctk.CTkFont(size=15, weight="bold"),
                                         text_color="#2fa572")
        self._result_lbl.pack(pady=10)

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=15)
        ctk.CTkButton(btn_f, text="✅ Confirm", fg_color="#2fa572", width=150, height=40,
                      command=self._confirm).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="#444444", width=100, height=40,
                      command=self.destroy).pack(side="left", padx=10)

    def _on_mkt_change(self, event=None):
        mkt = self._parse_val(self._mkt_var.get())
        pct = self._parse_val(self._buy_pct_var.get())
        cash = mkt * (pct / 100.0)
        self._flat_var.set(f"{cash:.2f}")
        self._result_lbl.configure(text=f"Cash to pay: ${cash:.2f}", text_color="#2fa572")

    def _on_pct_change(self, event=None):
        mkt = self._parse_val(self._mkt_var.get())
        pct = self._parse_val(self._buy_pct_var.get())
        cash = mkt * (pct / 100.0)
        self._flat_var.set(f"{cash:.2f}")
        self._result_lbl.configure(text=f"Cash to pay: ${cash:.2f}", text_color="#2fa572")

    def _on_flat_change(self, event=None):
        mkt = self._parse_val(self._mkt_var.get())
        cash = self._parse_val(self._flat_var.get())
        if mkt > 0:
            pct = (cash / mkt) * 100.0
            self._buy_pct_var.set(f"{pct:.1f}".rstrip('0').rstrip('.'))
        self._result_lbl.configure(text=f"Cash to pay: ${cash:.2f}", text_color="#2fa572")

    def _confirm(self):
        mkt = self._parse_val(self._mkt_var.get())
        cash = self._parse_val(self._flat_var.get())
        if mkt <= 0 or cash <= 0:
            messagebox.showerror("Invalid Input", "Please enter valid Market Value and Trade Cash amounts.", parent=self)
            return
        self.result = (mkt, cash)
        self.destroy()


class LiveCheckoutFrame(ctk.CTkFrame):
    """
    Dedicated Live POS tab: barcode scan → cart grid → full cash settlement panel.
    Mirrors the cash handling of PartialTradeView but on a single persistent screen.
    Supports Placeholder Trades which log PendingTrade records to the DB.
    """
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        self._cart_items = []           # list of InventoryItem objects
        self._placeholder_trades = []   # list of dicts for placeholder trades

        # Cash StringVars — all live-update NET DUE
        self._store_cash_var = tk.StringVar()
        self._cust_cash_var = tk.StringVar()
        self._tendered_var = tk.StringVar()
        self._discount_var = tk.StringVar()
        for v in [self._store_cash_var, self._cust_cash_var, self._tendered_var, self._discount_var]:
            v.trace_add("write", lambda *_: self._update_totals())

        settings = db_session.query(SystemSettings).first()
        self._buy_rate = settings.buy_percentage if settings else 0.70

        self._build_ui()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # ── LEFT: Scanner + Cart ─────────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color="#0F0F0F", corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Scanner bar
        scan_bar = ctk.CTkFrame(left, fg_color="#1A1A1A", corner_radius=8)
        scan_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        scan_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scan_bar, text="🔴 LIVE POS",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#EF4444").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))

        self._scan_entry = ctk.CTkEntry(scan_bar,
                                         placeholder_text="🔍 Scan barcode or type SKU, then press Enter",
                                         height=44, border_color="#333333",
                                         font=ctk.CTkFont(size=13))
        self._scan_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 12))
        self._scan_entry.bind("<Return>", self._handle_scan)

        # Hidden off-screen entry for hardware scanners that send <Return> without focus
        self._hidden_entry = tk.Entry(self, width=0)
        self._hidden_entry.place(x=-200, y=-200)
        self._hidden_entry.bind("<Return>", self._handle_hidden_scan)

        # Cart grid
        self._cart_scroll = ctk.CTkScrollableFrame(left, label_text="🛒  CURRENT CART",
                                                    fg_color="transparent")
        self._cart_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self._cart_scroll.grid_columnconfigure(0, weight=1)

        # Cart total + action buttons
        cart_footer = ctk.CTkFrame(left, fg_color="#1A1A1A", corner_radius=8)
        cart_footer.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        cart_footer.grid_columnconfigure((0, 1, 2), weight=1)

        self._cart_total_lbl = ctk.CTkLabel(cart_footer,
                                              text="Cart Total: $0.00",
                                              font=ctk.CTkFont(size=16, weight="bold"),
                                              text_color="#FFFFFF")
        self._cart_total_lbl.grid(row=0, column=0, columnspan=3, pady=(10, 6))

        ctk.CTkButton(cart_footer, text="💳 Add Placeholder Trade",
                      fg_color="#D97706", hover_color="#B45309",
                      font=ctk.CTkFont(weight="bold"), height=38,
                      command=self._add_placeholder_trade
                      ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkButton(cart_footer, text="🗑 Clear Cart",
                      fg_color="#444444", hover_color="#333333",
                      height=32, command=self._clear_cart
                      ).grid(row=2, column=0, sticky="ew", padx=(12, 4), pady=(0, 12))

        # ── RIGHT: Cash Settlement Panel ──────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color="#0F0F0F", corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="💵 CASH SETTLEMENT",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#2fa572").pack(pady=(16, 8), padx=16, anchor="w")

        fields_f = ctk.CTkFrame(right, fg_color="#1A1A1A", corner_radius=8)
        fields_f.pack(fill="x", padx=12, pady=4)
        fields_f.grid_columnconfigure(1, weight=1)

        def _lbl(row, text):
            ctk.CTkLabel(fields_f, text=text, anchor="e",
                         font=ctk.CTkFont(size=12)).grid(row=row, column=0, sticky="e", padx=(12, 6), pady=6)

        def _entry(row, var, color="#FFFFFF"):
            e = ctk.CTkEntry(fields_f, textvariable=var, width=140,
                             border_color="#333333", height=34,
                             text_color=color)
            e.grid(row=row, column=1, sticky="w", padx=(0, 12), pady=6)
            return e

        _lbl(0, "Store Cash Added ($):")
        _entry(0, self._store_cash_var, "#3b8ed0")
        _lbl(1, "Customer Cash Added ($):")
        _entry(1, self._cust_cash_var, "#3b8ed0")
        _lbl(2, "Discount Applied ($):")
        _entry(2, self._discount_var, "#EF4444")
        _lbl(3, "Cash Tendered ($):")
        _entry(3, self._tendered_var, "#EAB308")

        # Live NET DUE display
        totals_f = ctk.CTkFrame(right, fg_color="#1A1A1A", corner_radius=8)
        totals_f.pack(fill="x", padx=12, pady=8)

        self._net_due_lbl = ctk.CTkLabel(totals_f, text="NET DUE: $0.00",
                                          font=ctk.CTkFont(size=22, weight="bold"),
                                          text_color="#2fa572")
        self._net_due_lbl.pack(pady=(12, 4))

        self._change_lbl = ctk.CTkLabel(totals_f, text="Change Due: $0.00",
                                         font=ctk.CTkFont(size=16, weight="bold"),
                                         text_color="#EAB308")
        self._change_lbl.pack(pady=(0, 12))

        # Checkout buttons
        btn_f = ctk.CTkFrame(right, fg_color="transparent")
        btn_f.pack(fill="x", padx=12, pady=8)

        ctk.CTkButton(btn_f, text="✅ Checkout — Cash",
                      fg_color="#2fa572", hover_color="#237a54",
                      font=ctk.CTkFont(size=14, weight="bold"), height=50,
                      command=lambda: self._process_checkout("POS Cash")
                      ).pack(fill="x", pady=(0, 6))

        ctk.CTkButton(btn_f, text="🔄 Checkout — Trade",
                      fg_color="#3b8ed0", hover_color="#2d6fa8",
                      font=ctk.CTkFont(size=14, weight="bold"), height=50,
                      command=lambda: self._process_checkout("POS Trade")
                      ).pack(fill="x")

        self._refresh_cart()

    # ── Scanning ─────────────────────────────────────────────────────────────

    def _handle_scan(self, event=None):
        sku = self._scan_entry.get().strip()
        self._scan_entry.delete(0, tk.END)
        self._lookup_and_add(sku)

    def _handle_hidden_scan(self, event=None):
        sku = self._hidden_entry.get().strip()
        self._hidden_entry.delete(0, tk.END)
        self._lookup_and_add(sku)
        self.after(100, self._hidden_entry.focus_set)

    def _lookup_and_add(self, sku):
        if not sku:
            return
        item = db_session.query(InventoryItem).filter_by(sku=sku).first()
        if item and item.stock > 0:
            self._cart_items.append(item)
            self._refresh_cart()
        else:
            messagebox.showwarning("Not Found",
                                   f"SKU '{sku}' not found or out of stock.",
                                   parent=self)

    # ── Cart ─────────────────────────────────────────────────────────────────

    def _refresh_cart(self):
        for child in self._cart_scroll.winfo_children():
            child.destroy()

        for idx, item in enumerate(self._cart_items):
            row = ctk.CTkFrame(self._cart_scroll, fg_color="#2b2b2b", corner_radius=6)
            row.pack(fill="x", pady=2, padx=4)
            row.grid_columnconfigure(0, weight=1)

            sp = getattr(item, 'sticker_price', None)
            if sp is None:
                sp = float(item.price if item.price is not None else 0.0)
                
            if not hasattr(item, '_pos_price_override'):
                item._pos_price_override = tk.StringVar(value=f"{sp:.2f}")
                item._pos_price_override.trace_add("write", lambda *_: self._update_totals())
            
            ctk.CTkLabel(row, text=item.name, anchor="w",
                         font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="ew", padx=10, pady=6)
            
            ctk.CTkLabel(row, text="$", text_color="#2fa572").grid(row=0, column=1, sticky="e")
            ctk.CTkEntry(row, textvariable=item._pos_price_override, width=60, height=26,
                         border_color="#333333", text_color="#2fa572").grid(row=0, column=2, padx=(2, 8))
            ctk.CTkButton(row, text="✕", width=26, height=26,
                          fg_color="#944747", hover_color="#7A3A3A",
                          command=lambda i=idx: self._remove_item(i)
                          ).grid(row=0, column=3, padx=(0, 8))

        for idx, trade in enumerate(self._placeholder_trades):
            row = ctk.CTkFrame(self._cart_scroll, fg_color="#1A1200", border_width=1, border_color="#D97706", corner_radius=6)
            row.pack(fill="x", pady=4, padx=4)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row, text=f"💳 Placeholder Trade (Mkt: ${trade['market_value']:.2f})", anchor="w",
                         text_color="#EAB308", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=6)

            rate_var = tk.StringVar(value=str(int(trade['rate'] * 100)))
            val_lbl = ctk.CTkLabel(row, text=f"-${trade['market_value'] * trade['rate']:.2f}",
                                   text_color="#EAB308", font=ctk.CTkFont(weight="bold"), width=60, anchor="e")

            def on_trade_rate_change(*args, i=idx, v=rate_var, l=val_lbl, mv=trade['market_value']):
                try:
                    new_rate = float(v.get()) / 100.0
                    old_rate = self._placeholder_trades[i].get('rate', 0.0)
                    self._placeholder_trades[i]['rate'] = new_rate
                    new_val = mv * new_rate
                    l.configure(text=f"-${new_val:.2f}")
                    pt_id = self._placeholder_trades[i].get('pending_trade_id')
                    if pt_id:
                        try:
                            from database import db_session, PendingTrade
                            pt = db_session.query(PendingTrade).get(pt_id)
                            if pt:
                                old_val = mv * old_rate
                                pt.total_cash_paid = max(0.0, pt.total_cash_paid - old_val + new_val)
                                db_session.commit()
                        except:
                            db_session.rollback()
                    self._update_totals()
                except ValueError:
                    pass

            rate_var.trace_add("write", on_trade_rate_change)

            ctk.CTkLabel(row, text="Rate %:", text_color="#EAB308").grid(row=0, column=1, padx=(10, 2))
            ctk.CTkEntry(row, textvariable=rate_var, width=40, height=24, border_color="#D97706", text_color="#EAB308").grid(row=0, column=2, padx=2)
            val_lbl.grid(row=0, column=3, padx=10)

            ctk.CTkButton(row, text="✕", width=26, height=26,
                          fg_color="#944747", hover_color="#7A3A3A",
                          command=lambda i=idx: self._remove_placeholder(i)
                          ).grid(row=0, column=4, padx=(0, 8))

        self._update_totals()

    def _remove_item(self, idx):
        if 0 <= idx < len(self._cart_items):
            self._cart_items.pop(idx)
        self._refresh_cart()

    def _remove_placeholder(self, idx):
        if 0 <= idx < len(self._placeholder_trades):
            item = self._placeholder_trades.pop(idx)
            pt_id = item.get('pending_trade_id')
            if pt_id:
                try:
                    from database import db_session, PendingTrade
                    pt = db_session.query(PendingTrade).get(pt_id)
                    if pt:
                        val = item['market_value'] * item.get('rate', self._buy_rate)
                        pt.total_market_value = max(0.0, pt.total_market_value - item['market_value'])
                        pt.total_cash_paid = max(0.0, pt.total_cash_paid - val)
                        if pt.total_market_value == 0 and pt.total_cash_paid == 0:
                            db_session.delete(pt)
                        db_session.commit()
                except Exception as e:
                    db_session.rollback()
                    print(f"[LivePOS] Error removing placeholder: {e}")
        self._refresh_cart()

    def _clear_cart(self):
        self._cart_items.clear()
        self._placeholder_trades.clear()
        self._refresh_cart()

    # ── Placeholder Trade ─────────────────────────────────────────────────────

    def _add_placeholder_trade(self):
        dlg = PlaceholderTradeDialog(self.winfo_toplevel(), self._buy_rate)
        self.wait_window(dlg)
        if dlg.result:
            mkt_val, cash_paid = dlg.result
            try:
                from database import db_session, PendingTrade
                trade = db_session.query(PendingTrade).filter_by(status='pending').first()
                if trade:
                    trade.total_market_value += mkt_val
                    trade.total_cash_paid += cash_paid
                else:
                    trade = PendingTrade(total_market_value=mkt_val, total_cash_paid=cash_paid)
                    db_session.add(trade)
                db_session.commit()
                trade_id = trade.id
            except Exception as e:
                db_session.rollback()
                print(f"[LivePOS] PendingTrade save error: {e}")
                trade_id = None

            rate = cash_paid / mkt_val if mkt_val > 0 else self._buy_rate
            self._placeholder_trades.append({
                "name": "Placeholder Trade",
                "market_value": mkt_val,
                "rate": rate,
                "pending_trade_id": trade_id
            })
            self._refresh_cart()

    # ── Math ──────────────────────────────────────────────────────────────────

    def _update_totals(self):
        cart_total = 0.0
        for i in self._cart_items:
            try:
                cart_total += float(i._pos_price_override.get())
            except (ValueError, AttributeError):
                pass
        placeholder_cost = sum(t['market_value'] * t['rate'] for t in self._placeholder_trades)

        def _float(var):
            try:
                return float(var.get())
            except ValueError:
                return 0.0

        store_cash = _float(self._store_cash_var)
        cust_cash = _float(self._cust_cash_var)
        tendered = _float(self._tendered_var)
        discount = _float(self._discount_var)

        self._cart_total_lbl.configure(text=f"Cart Total: ${cart_total:.2f}")

        net = cart_total - placeholder_cost + store_cash - cust_cash - discount
        color = "#2fa572" if net >= 0 else "#EF4444"
        self._net_due_lbl.configure(text=f"NET DUE: ${net:.2f}", text_color=color)

        if tendered > 0 and net >= 0:
            change = tendered - net
            self._change_lbl.configure(text=f"Change Due: ${change:.2f}")
        else:
            self._change_lbl.configure(text="Change Due: $0.00")

    # ── Checkout ──────────────────────────────────────────────────────────────

    def _process_checkout(self, transaction_type: str):
        if not self._cart_items and not self._placeholder_trades:
            messagebox.showwarning("Empty Cart", "Add items or trades to the cart first.", parent=self)
            return

        def _float(var):
            try:
                return float(var.get())
            except ValueError:
                return 0.0

        store_cash = _float(self._store_cash_var)
        cust_cash = _float(self._cust_cash_var)
        discount = _float(self._discount_var)
        placeholder_cost = sum(t['market_value'] * t['rate'] for t in self._placeholder_trades)
        
        cart_total = 0.0
        for i in self._cart_items:
            try:
                cart_total += float(i._pos_price_override.get())
            except (ValueError, AttributeError):
                pass
                
        net_due = cart_total - placeholder_cost + store_cash - cust_cash - discount

        confirm = messagebox.askyesno(
            "Confirm Checkout",
            f"Transaction Type: {transaction_type}\n"
            f"Cart Total: ${cart_total:.2f}\n"
            f"Placeholder Trade Cost: -${placeholder_cost:.2f}\n"
            f"Discount: -${discount:.2f}\n"
            f"NET DUE: ${net_due:.2f}\n\n"
            f"Proceed with checkout?",
            parent=self
        )
        if not confirm:
            return

        try:
            from database import SyncOutbox
            for item in self._cart_items:
                item.stock -= 1
                
                try:
                    sale_price = float(item._pos_price_override.get())
                except (ValueError, AttributeError):
                    sale_price = float(getattr(item, 'sticker_price', item.price) or 0.0)
                    
                if cart_total > 0 and discount > 0:
                    item_discount = (sale_price / cart_total) * discount
                    sale_price = max(0.0, sale_price - item_discount)
                    
                cost_basis = float(item.cost if item.cost is not None else 0.0)
                
                db_session.add(Sale(
                    item_name=item.name,
                    sku=item.sku,
                    sold_price=sale_price,
                    profit=sale_price - cost_basis,
                    transaction_type=transaction_type,
                    trade_in_value=placeholder_cost,
                    net_revenue=net_due
                ))
                db_session.add(SyncOutbox(
                    action_type='stock_update',
                    sku=item.sku,
                    quantity_change=-1,
                    new_price=0.0
                ))

            db_session.commit()

            # Trigger background Shopify sync
            def _delayed_sync():
                import time as _time
                _time.sleep(3)
                if core_manager:
                    core_manager._process_sync_outbox()
            import threading
            threading.Thread(target=_delayed_sync, daemon=True).start()

            self._clear_cart()
            self.refresh_callback()
            messagebox.showinfo("✅ Success",
                                f"{transaction_type} complete!\n{len(self._cart_items or [])} items sold.",
                                parent=self)

        except Exception as e:
            db_session.rollback()
            messagebox.showerror("Error", f"Checkout failed: {e}", parent=self)




class InventoryManagerFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Header & Stats
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.count_lbl = ctk.CTkLabel(self.header_frame, text="TOTAL ITEMS: 0", font=ctk.CTkFont(weight="bold"))
        self.count_lbl.pack(side="left", padx=10)
        
        self.value_lbl = ctk.CTkLabel(self.header_frame, text="TOTAL VALUE: $0.00", font=ctk.CTkFont(weight="bold"), text_color="#2fa572")
        self.value_lbl.pack(side="left", padx=20)

        # Actions Button Container
        self.btn_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.btn_container.pack(side="right", padx=10)

        # Approve All Images Button (hidden by default)
        self.approve_all_btn = ctk.CTkButton(self.btn_container, text="✅ Approve All Images", command=self.run_approve_all, fg_color="#2fa572", hover_color="#268a5f", font=ctk.CTkFont(weight="bold"))
        self.approve_all_btn.grid(row=0, column=0, padx=5)
        self.approve_all_btn.grid_remove()

        # Validate & Fetch Images Button moved to SettingsFrame

        # Verify Shopify Status Button
        self.verify_shopify_btn = ctk.CTkButton(self.btn_container, text="🔍 Verify Shopify Status", command=self.run_verify_shopify_status, fg_color="#F59E0B", hover_color="#D97706", font=ctk.CTkFont(weight="bold"))
        self.verify_shopify_btn.grid(row=0, column=2, padx=5)

        # Capture Show Prices Button
        self.capture_prices_btn = ctk.CTkButton(self.btn_container, text="📸 Capture Show Prices", command=self.run_capture_show_prices, fg_color="#E11D48", hover_color="#BE123C", font=ctk.CTkFont(weight="bold"))
        self.capture_prices_btn.grid(row=0, column=3, padx=5)

        # Collectr Recon Button
        self.recon_btn = ctk.CTkButton(self.btn_container, text="🔄 Run Recon", command=self.run_collectr_reconciliation, fg_color="#3b8ed0", hover_color="#2c6a9b", font=ctk.CTkFont(weight="bold"))
        self.recon_btn.grid(row=0, column=4, padx=5)

        # Force Sync Button
        self.sync_btn = ctk.CTkButton(self.btn_container, text="🚀 Force Sync", command=self.run_force_sync, fg_color="#8B5CF6", hover_color="#7C3AED", font=ctk.CTkFont(weight="bold"))
        self.sync_btn.grid(row=0, column=5, padx=5)

        # Mark All Restickered Button
        self.mark_all_restickered_btn = ctk.CTkButton(self.btn_container, text="✅ Mark All Restickered", command=self.run_mark_all_restickered, fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(weight="bold"))
        self.mark_all_restickered_btn.grid(row=0, column=6, padx=5)

        # Graded Card Price Wizard Button (Hidden by default)
        self.graded_wizard_btn = ctk.CTkButton(self.btn_container, text="✨ Graded Price Wizard", command=self.open_graded_wizard, fg_color="#F2A900", hover_color="#C88A00", font=ctk.CTkFont(weight="bold"))
        self.graded_wizard_btn.grid(row=0, column=7, padx=5)
        self.graded_wizard_btn.grid_remove()
        self.mark_all_restickered_btn.grid_remove()

        # Approve under $5 Button
        self.approve_under_5_btn = ctk.CTkButton(self.btn_container, text="✅ Accept < $5 Changes", command=self.run_approve_under_5, fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(weight="bold"))
        self.approve_under_5_btn.grid(row=0, column=7, padx=5)
        self.approve_under_5_btn.grid_remove()

        # Generate All QR Codes Button
        self.generate_all_qr_btn = ctk.CTkButton(self.btn_container, text="Generate all QR Codes", command=self.run_generate_all_qr, fg_color="#F59E0B", hover_color="#D97706", font=ctk.CTkFont(weight="bold"))
        self.generate_all_qr_btn.grid(row=0, column=8, padx=5)
        self.generate_all_qr_btn.grid_remove()

        # Progress Frame (initially hidden)
        self.progress_frame = ctk.CTkFrame(self, fg_color="#18181B", border_width=1, border_color="#374151", corner_radius=8)
        self.progress_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.progress_frame.grid_columnconfigure(1, weight=1)
        self.progress_frame.grid_remove()

        self.progress_lbl = ctk.CTkLabel(self.progress_frame, text="Sync Progress: 0 / 0 (0 left)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10B981")
        self.progress_lbl.grid(row=0, column=0, padx=15, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color="#10B981", fg_color="#27272A", height=12)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(10, 15), pady=10)
        self.progress_bar.set(0)

        # Pagination & Sorting variables
        self.current_page = 1
        self.page_size = 10
        self.sort_var = ctk.StringVar(value="Newest First")
        
        # Search & Sort Row
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.filter_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(self.filter_frame, placeholder_text="Filter Inventory by Name, SKU, or Set...", height=35, border_color="#333333")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", lambda e: self.reset_page_and_refresh())
        
        self.sort_dropdown = ctk.CTkOptionMenu(
            self.filter_frame, 
            variable=self.sort_var, 
            values=["Newest First", "Price (High-Low)", "Price (Low-High)", "Name (A-Z)", "Set (A-Z)", "Missing Image"],
            command=lambda v: self.reset_page_and_refresh()
        , button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00")
        self.sort_dropdown.grid(row=0, column=1, sticky="e")

        self.game_filter_var = ctk.StringVar(value="All Games")
        self.game_filter_dropdown = ctk.CTkOptionMenu(
            self.filter_frame, 
            variable=self.game_filter_var, 
            values=["All Games", "Pokemon", "One Piece"],
            command=lambda v: self.reset_page_and_refresh(),
            button_color="#2fa572", button_hover_color="#268a5f", dropdown_hover_color="#268a5f"
        )
        self.game_filter_dropdown.grid(row=0, column=2, sticky="e", padx=(5, 0))

        # Sub-tab selector
        self.filter_var = ctk.StringVar(value="Singles")
        self.seg_btn = ctk.CTkSegmentedButton(self, values=["Singles", "Graded", "Sealed", "Updated Cards", "Needs Restickering"], variable=self.filter_var, command=lambda v: self.reset_page_and_refresh())
        self.seg_btn.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

        # List
        self.list_frame = ctk.CTkScrollableFrame(self, label_text="ACTIVE VAULT INVENTORY (STOCK > 0)")
        self.list_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        self.list_frame.grid_columnconfigure(0, weight=0, minsize=100)
        self.list_frame.grid_columnconfigure(1, weight=1, minsize=150)
        self.list_frame.grid_columnconfigure(2, weight=1, minsize=100)
        self.list_frame.grid_columnconfigure((3,4,5,6,7,8), weight=0, minsize=60)
        
        # Pagination Controls
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.pagination_frame.grid_columnconfigure(1, weight=1)
        
        self.prev_btn = ctk.CTkButton(self.pagination_frame, text="⬅️ Previous", width=100, command=self.prev_page)
        self.prev_btn.grid(row=0, column=0, sticky="w")
        
        self.page_lbl = ctk.CTkLabel(self.pagination_frame, text="Page 1 of 1", font=ctk.CTkFont(weight="bold"))
        self.page_lbl.grid(row=0, column=1, padx=10)
        
        self.next_btn = ctk.CTkButton(self.pagination_frame, text="Next ➡️", width=100, command=self.next_page)
        self.next_btn.grid(row=0, column=2, sticky="e", padx=(0, 5))

        self.last_btn = ctk.CTkButton(self.pagination_frame, text="Last ⏭️", width=100, command=self.last_page)
        self.last_btn.grid(row=0, column=3, sticky="e")

        self.after(100, self.refresh_list)

    def run_force_sync(self):
        import threading
        
        # Change button color to indicate working state
        self.sync_btn.configure(text="⏳ Syncing...", fg_color="#6B7280", hover_color="#4B5563", state="disabled")
        self.progress_frame.grid()
        self.progress_lbl.configure(text="Calculating items to sync...")
        self.progress_bar.set(0)

        try:
            shopify_frame = self.master.master.frames.get("shopify")
            if shopify_frame:
                shopify_frame.sync_btn.configure(text="⏳ Syncing...", fg_color="#6B7280", hover_color="#4B5563", state="disabled")
                shopify_frame.progress_frame.grid()
                shopify_frame.progress_lbl.configure(text="Calculating items to sync...")
                shopify_frame.progress_bar.set(0)
        except Exception:
            shopify_frame = None

        def progress_callback(current, total, item_name=""):
            def update_ui():
                left = total - current
                pct = (current / total) if total > 0 else 0
                txt = f"Sync Progress: {current} / {total} ({left} left)"
                if item_name:
                    txt += f" - {item_name}"
                self.progress_lbl.configure(text=txt)
                self.progress_bar.set(pct)
                if shopify_frame:
                    shopify_frame.progress_lbl.configure(text=txt)
                    shopify_frame.progress_bar.set(pct)
            self.after(0, update_ui)
        
        def sync_worker():
            try:
                # Use global core_manager instance directly
                if core_manager:
                    core_manager._process_sync_outbox(progress_callback=progress_callback)
            except Exception as e:
                print(f"Force sync error: {e}")
            finally:
                # Restore button and refresh list to apply color changes
                def restore_ui():
                    self.sync_btn.configure(text="🚀 Force Sync", fg_color="#8B5CF6", hover_color="#7C3AED", state="normal")
                    self.progress_frame.grid_remove()
                    if shopify_frame:
                        shopify_frame.sync_btn.configure(text="🚀 Force Sync", fg_color="#8B5CF6", hover_color="#7C3AED", state="normal")
                        shopify_frame.progress_frame.grid_remove()
                        shopify_frame.refresh_list()
                    self.refresh_list()
                    if self.refresh_callback:
                        self.refresh_callback()
                self.after(0, restore_ui)
                
        threading.Thread(target=sync_worker, daemon=True).start()

    def run_approve_all(self):
        from database import db_session, InventoryItem, StagingItem
        import tkinter.messagebox as messagebox
        
        # Lock all unlocked items
        inv_items = db_session.query(InventoryItem).filter(InventoryItem.image_locked == False).all()
        for i in inv_items:
            i.image_locked = True
            
        stg_items = db_session.query(StagingItem).filter(StagingItem.image_locked == False).all()
        for i in stg_items:
            i.image_locked = True
            
        db_session.commit()
        messagebox.showinfo("Approved", f"Locked {len(inv_items) + len(stg_items)} cards. They will no longer be modified by automatic fetches.")
        self.refresh_list()

    def run_generate_all_qr(self):
        import threading
        import os
        from logic import generate_item_barcode
        from database import db_session, InventoryItem
        
        self.generate_all_qr_btn.configure(state="disabled", text="Generating...")
        
        def _worker():
            try:
                base_path = os.path.dirname(__file__)
                items = db_session.query(InventoryItem).filter(InventoryItem.stock > 0).all()
                for item in items:
                    path = os.path.join(base_path, 'static', 'barcodes', f"{item.sku}.png")
                    if not os.path.exists(path):
                        generate_item_barcode(item.sku, market_price=item.price, format="QR")
                self.after(0, self.refresh_list)
            except Exception as e:
                print(f"Error generating QRs: {e}")
            finally:
                self.after(0, lambda: self.generate_all_qr_btn.configure(state="normal", text="Generate all QR Codes"))
                
        threading.Thread(target=_worker, daemon=True).start()


    def run_verify_shopify_status(self):
        from tkinter import messagebox
        import threading
        from database import db_session, InventoryItem
        from services.shopify_client import ShopifyClient
        
        self.verify_shopify_btn.configure(state="disabled", text="Verifying...")
        
        def _worker():
            try:
                client = ShopifyClient()
                variants = client.fetch_all_variants()
                active_skus = {k: v['inventory_quantity'] for k, v in variants.items()}
                
                # Find local items that think they are synced
                synced_items = db_session.query(InventoryItem).filter(InventoryItem.sync_status.in_(['synced', 'active'])).all()
                flagged_count = 0
                
                for item in synced_items:
                    if item.sku and item.sku not in active_skus:
                        # Card was deleted on Shopify! Move back to paused/review.
                        item.sync_status = 'paused'
                        item.needs_update = True
                        flagged_count += 1
                    elif item.sku and item.sku in active_skus:
                        # Card exists, check quantity
                        shopify_qty = active_skus[item.sku]
                        needs_stock_update = item.stock != shopify_qty
                        
                        shop_var = variants[item.sku]
                        shop_has_images = shop_var.get('has_images', False)
                        
                        local_img = getattr(item, 'custom_image_url', None) or getattr(item, 'image_url', None)
                        import os
                        has_valid_img = local_img and (str(local_img).startswith('http') or os.path.exists(local_img))
                        needs_image_update = has_valid_img and not shop_has_images
                        
                        from database import SyncOutbox
                        if needs_image_update:
                            print(f"[*] Missing Image detected for {item.sku}. Queued sync.")
                            outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=item.price)
                            db_session.add(outbox)
                        elif needs_stock_update:
                            # Quantity mismatch detected! Queue an overriding stock update.
                            diff = item.stock - shopify_qty
                            outbox = SyncOutbox(action_type='stock_update', sku=item.sku, quantity_change=diff, new_price=0.0)
                            db_session.add(outbox)
                            print(f"[*] Audit Mismatch: {item.sku} (Local: {item.stock}, Shopify: {shopify_qty}). Queued sync.")
                        
                db_session.commit()
                self.after(0, lambda: messagebox.showinfo("Verification Complete", f"Shopify status verified.\nFlagged {flagged_count} missing SKUs."))
                self.after(0, self.refresh_list)
            except Exception as e:
                error_msg = str(e)
                import traceback
                traceback.print_exc()
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to verify Shopify status: {error_msg}"))
            finally:
                def reset_btn():
                    try:
                        self.verify_shopify_btn.configure(state="normal", text="🔍 Verify Shopify Status")
                    except Exception:
                        pass
                self.after(0, reset_btn)
                
        threading.Thread(target=_worker, daemon=True).start()

    def run_capture_show_prices(self):
        from tkinter import messagebox
        import customtkinter as ctk
        from datetime import datetime
        import threading

        win = ctk.CTkToplevel(self)
        win.title("Show Price Captures Manager")
        win.geometry("750x580")
        win.attributes("-topmost", True)
        win.grab_set()

        # Header Frame
        header_frame = ctk.CTkFrame(win, fg_color="#1E293B", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(header_frame, text="📸 Show Price Captures Manager", font=ctk.CTkFont(size=20, weight="bold"), text_color="#FFFFFF")
        title_lbl.pack(pady=(15, 5), padx=15, anchor="w")

        desc_lbl = ctk.CTkLabel(
            header_frame, 
            text="Take a snapshot of current market prices (rounded to nearest dollar) for all in-stock cards.\nYou can apply past captures to restore previous sticker prices or manage your capture history.", 
            font=ctk.CTkFont(size=12), 
            text_color="#94A3B8",
            justify="left"
        )
        desc_lbl.pack(pady=(0, 15), padx=15, anchor="w")

        # Create Button Frame
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 10))

        list_frame = ctk.CTkScrollableFrame(win, label_text="SAVED PRICE CAPTURES", label_font=ctk.CTkFont(weight="bold"))
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        def refresh_captures():
            for widget in list_frame.winfo_children():
                widget.destroy()

            try:
                from database import db_session, ShowPriceCapture
                captures = db_session.query(ShowPriceCapture).order_by(ShowPriceCapture.timestamp.desc()).all()

                if not captures:
                    empty_lbl = ctk.CTkLabel(list_frame, text="No price captures saved yet. Create a new snapshot above!", font=ctk.CTkFont(size=14, slant="italic"), text_color="#64748B")
                    empty_lbl.pack(pady=40)
                    return

                for idx, cap in enumerate(captures):
                    row_frame = ctk.CTkFrame(list_frame, fg_color="#1E1E1E" if idx % 2 == 0 else "#252525", corner_radius=6)
                    row_frame.pack(fill="x", padx=5, pady=5)

                    info_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)

                    time_str = cap.timestamp.strftime('%Y-%m-%d %H:%M:%S') if cap.timestamp else "Unknown Date"
                    name_lbl = ctk.CTkLabel(info_frame, text=f"{cap.name}", font=ctk.CTkFont(size=15, weight="bold"), text_color="#E2E8F0")
                    name_lbl.pack(anchor="w")

                    meta_lbl = ctk.CTkLabel(info_frame, text=f"Captured: {time_str} | Items: {cap.item_count} | Total Baseline Value: ${cap.total_value:,.2f}", font=ctk.CTkFont(size=12), text_color="#94A3B8")
                    meta_lbl.pack(anchor="w", pady=(2, 0))

                    actions_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    actions_frame.pack(side="right", padx=15, pady=10)

                    apply_btn = ctk.CTkButton(
                        actions_frame, 
                        text="✅ Apply Capture", 
                        fg_color="#10B981", 
                        hover_color="#059669", 
                        font=ctk.CTkFont(weight="bold"), 
                        width=120,
                        command=lambda c=cap: apply_capture(c)
                    )
                    apply_btn.pack(side="left", padx=(0, 10))

                    delete_btn = ctk.CTkButton(
                        actions_frame, 
                        text="❌ Delete", 
                        fg_color="#EF4444", 
                        hover_color="#DC2626", 
                        font=ctk.CTkFont(weight="bold"), 
                        width=80,
                        command=lambda c=cap: delete_capture(c)
                    )
                    delete_btn.pack(side="left")

            except Exception as e:
                err_lbl = ctk.CTkLabel(list_frame, text=f"Error loading captures: {e}", text_color="#EF4444")
                err_lbl.pack(pady=20)

        def create_new_capture():
            dialog = ctk.CTkInputDialog(text="Enter a name for this price capture snapshot:\n(Leave blank for default date name)", title="Create Capture")
            user_input = dialog.get_input()
            if user_input is None:
                return # User cancelled
                
            default_name = f"Show Capture - {datetime.now().strftime('%b %d, %Y')}"
            capture_name = user_input.strip() if user_input.strip() else default_name

            create_btn.configure(state="disabled", text="📸 Capturing...")
            
            def _worker():
                try:
                    from database import db_session, InventoryItem, ShowPriceCapture, ShowPriceCaptureItem
                    items = db_session.query(InventoryItem).filter(InventoryItem.stock > 0).all()
                    
                    if not items:
                        win.after(0, lambda: messagebox.showwarning("Empty Inventory", "No in-stock items found to capture."))
                        return

                    new_cap = ShowPriceCapture(
                        name=capture_name,
                        timestamp=datetime.now(),
                        item_count=len(items),
                        total_value=0.0
                    )
                    db_session.add(new_cap)
                    db_session.flush() # get new_cap.id

                    import math
                    total_val = 0.0
                    for item in items:
                        rounded_price = float(math.ceil(item.price if item.price is not None else 0.0))
                        item.sticker_price = rounded_price # apply immediately
                        total_val += rounded_price * item.stock
                        
                        cap_item = ShowPriceCaptureItem(
                            capture_id=new_cap.id,
                            sku=item.sku,
                            sticker_price=rounded_price
                        )
                        db_session.add(cap_item)

                    new_cap.total_value = total_val
                    db_session.commit()

                    win.after(0, lambda: messagebox.showinfo("Success", f"Created price capture '{capture_name}' with {len(items)} items and applied to inventory!"))
                    win.after(0, refresh_captures)
                    win.after(0, self.refresh_list)
                except Exception as e:
                    win.after(0, lambda: messagebox.showerror("Error", f"Failed to create capture: {e}"))
                finally:
                    win.after(0, lambda: create_btn.configure(state="normal", text="📸 Create New Capture Snapshot"))

            threading.Thread(target=_worker, daemon=True).start()

        def apply_capture(cap):
            if not messagebox.askyesno("Apply Capture", f"Are you sure you want to apply '{cap.name}'?\n\nThis will overwrite the current sticker price baseline for all matching items in your inventory."):
                return

            try:
                from database import db_session, InventoryItem, ShowPriceCaptureItem
                cap_items = db_session.query(ShowPriceCaptureItem).filter_by(capture_id=cap.id).all()
                cap_dict = {ci.sku: ci.sticker_price for ci in cap_items}

                items = db_session.query(InventoryItem).filter(InventoryItem.stock > 0).all()
                match_count = 0
                for item in items:
                    if item.sku in cap_dict:
                        item.sticker_price = cap_dict[item.sku]
                        match_count += 1

                db_session.commit()
                messagebox.showinfo("Success", f"Successfully applied captured prices to {match_count} inventory items!")
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to apply capture: {e}")

        def delete_capture(cap):
            if not messagebox.askyesno("Delete Capture", f"Are you sure you want to delete '{cap.name}'?\n\nThis will remove the snapshot from history, but will not change current inventory sticker prices."):
                return

            try:
                from database import db_session, ShowPriceCapture, ShowPriceCaptureItem
                db_session.query(ShowPriceCaptureItem).filter_by(capture_id=cap.id).delete()
                db_session.delete(cap)
                db_session.commit()
                messagebox.showinfo("Success", "Capture snapshot deleted successfully.")
                refresh_captures()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete capture: {e}")

        create_btn = ctk.CTkButton(
            btn_frame, 
            text="📸 Create New Capture Snapshot", 
            fg_color="#2563EB", 
            hover_color="#1D4ED8", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=create_new_capture
        )
        create_btn.pack(fill="x")

        refresh_captures()

    def open_graded_wizard(self):
        from graded_wizard_module import GradedCardWizard
        GradedCardWizard(self)

    def run_collectr_reconciliation(self):
        from tkinter import filedialog, messagebox
        import os
        from reconciliation_engine import process_reconciliation

        csv_path = filedialog.askopenfilename(
            parent=self,
            title="Select Collectr Export CSV",
            filetypes=[("CSV files", "*.csv")],
            initialdir=os.path.expanduser("~")
        )
        if not csv_path:
            return

        # Disable button while running
        self.recon_btn.configure(state="disabled", text="⏳ Running...")
        self.update_idletasks()

        try:
            result = process_reconciliation(csv_path)
        except Exception as e:
            messagebox.showerror("Error", f"Reconciliation engine crashed: {e}")
            self.recon_btn.configure(state="normal", text="📊 Run Recon")
            return
        finally:
            self.recon_btn.configure(state="normal", text="📊 Run Recon")

        if not result.get("success"):
            messagebox.showerror("Error", "Failed to run reconciliation engine. Check the console for details.")
            return

        prices_updated = result.get("prices_updated", 0)
        removal_list = result.get("removal_list", {})
        add_list = result.get("missing_from_collectr", {})
        unknown_cards = result.get("unknown_cards", [])

        # --- Send unknown cards to staging ---
        if unknown_cards:
            try:
                from logic import add_item_to_staging
                import sys, os
                img_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image_db_manager')
                if img_db_path not in sys.path:
                    sys.path.append(img_db_path)
                try:
                    import db_handler as img_db_handler
                except ImportError:
                    img_db_handler = None
                    
                staged_count = 0
                for card in unknown_cards:
                    img_path = None
                    if img_db_handler:
                        img_path = img_db_handler.find_image_by_set_and_number(
                            card["set_name"], card["card_number"], card_name=card["name"]
                        )
                        
                    staging_data = {
                        "name": card["name"],
                        "set_name": card["set_name"],
                        "sequence_number": card["card_number"],
                        "market_price": card["price"],
                        "card_type": card.get("card_type", "Single"),
                        "variant": card.get("variant", "Normal"),
                        "condition": card.get("condition", "NM"),
                        "quantity": card.get("quantity", 1),
                        "needs_review": True,
                        "confidence_scores": {},
                    }
                    if img_path and os.path.exists(img_path):
                        staging_data["image_path"] = img_path
                        
                    add_item_to_staging(staging_data)
                    staged_count += 1
                # Refresh staging dock
                try:
                    self.winfo_toplevel().frames["studio"].refresh_staging_dock()
                except Exception:
                    pass
                print(f"[*] Staged {staged_count} unknown Collectr cards for review.")
            except Exception as e:
                print(f"[!] Error staging unknown cards: {e}")

        # --- Populate Cards-to-Remove panel ---
        app = self.winfo_toplevel()
        if removal_list:
            if hasattr(app, "show_remove_panel"):
                app.show_remove_panel(removal_list)
                
        # --- Populate Cards-to-Add panel ---
        if add_list:
            if hasattr(app, "show_add_panel"):
                app.show_add_panel(add_list)

        # --- Summary toast ---
        parts = []
        if prices_updated:
            parts.append(f"{prices_updated} price update(s)")
        if removal_list:
            total_rm = sum(len(v) for v in removal_list.values())
            parts.append(f"{total_rm} card(s) to remove from Collectr")
        if add_list:
            total_add = sum(len(v) for v in add_list.values())
            parts.append(f"{total_add} card(s) missing from Collectr")
        if unknown_cards:
            parts.append(f"{len(unknown_cards)} unknown card(s) sent to Staging")
        if not parts:
            parts.append("No changes needed — everything is up to date!")

        messagebox.showinfo("Recon Complete", "\n".join(parts))


    def reset_page_and_refresh(self):
        self.current_page = 1
        self.refresh_list()
        self.after(10, lambda: self.list_frame._parent_canvas.yview_moveto(0))

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_list()
            self.after(10, lambda: self.list_frame._parent_canvas.yview_moveto(0))

    def next_page(self):
        self.current_page += 1
        self.refresh_list()
        self.after(10, lambda: self.list_frame._parent_canvas.yview_moveto(0))

    def last_page(self):
        # We need to compute total pages using the active query
        query = self.search_entry.get().lower()
        active_tab = self.filter_var.get()
        base_query = db_session.query(InventoryItem).filter(
            (InventoryItem.name.ilike(f"%{query}%")) | (InventoryItem.sku.ilike(f"%{query}%")) | (InventoryItem.set_name.ilike(f"%{query}%"))
        ).filter(InventoryItem.stock > 0)
        
        if active_tab == "Sealed":
            base_query = base_query.filter(InventoryItem.card_type == 'Sealed')
        elif active_tab == "Graded":
            base_query = base_query.filter(InventoryItem.card_type == 'Graded')
        elif active_tab == "Updated Cards":
            base_query = base_query.filter(InventoryItem.needs_update == True)
        else:
            base_query = base_query.filter((InventoryItem.card_type != 'Sealed') & (InventoryItem.card_type != 'Graded') | (InventoryItem.card_type == None))
            
        if self.sort_var.get() == "Missing Image":
            base_query = base_query.filter((InventoryItem.image_url == None) | (InventoryItem.image_url == ""))
            
        total_unique_items = base_query.count()
        import math
        total_pages = math.ceil(total_unique_items / self.page_size) if total_unique_items > 0 else 1
        
        if total_pages > 0 and self.current_page != total_pages:
            self.current_page = total_pages
            self.refresh_list()
            self.after(10, lambda: self.list_frame._parent_canvas.yview_moveto(0))

    def refresh_list(self):
        for child in self.list_frame.winfo_children(): child.destroy()
        query = self.search_entry.get().lower()
        active_tab = self.filter_var.get()
        
        if active_tab == "Graded":
            self.graded_wizard_btn.grid()
        else:
            self.graded_wizard_btn.grid_remove()
        
        # FILTER FOR STOCK > 0
        base_query = db_session.query(InventoryItem).filter(
            (InventoryItem.name.ilike(f"%{query}%")) | (InventoryItem.sku.ilike(f"%{query}%")) | (InventoryItem.set_name.ilike(f"%{query}%"))
        ).filter(InventoryItem.stock > 0)
        
        game_filter = getattr(self, 'game_filter_var', None)
        if game_filter and game_filter.get() != "All Games":
            base_query = base_query.filter(InventoryItem.game == game_filter.get())
        
        if active_tab == "Sealed":
            base_query = base_query.filter(InventoryItem.card_type == 'Sealed')
        elif active_tab == "Graded":
            base_query = base_query.filter(InventoryItem.card_type == 'Graded')
        elif active_tab == "Updated Cards":
            base_query = base_query.filter(InventoryItem.needs_update == True)
        elif active_tab == "Needs Restickering":
            from sqlalchemy import func
            from database import SystemSettings
            settings = db_session.query(SystemSettings).first()
            threshold = settings.resticker_threshold if settings and settings.resticker_threshold is not None else 2.00
            base_query = base_query.filter(InventoryItem.sticker_price.isnot(None), func.abs(InventoryItem.sticker_price - func.ceil(InventoryItem.price)) >= threshold)
        else:
            base_query = base_query.filter((InventoryItem.card_type != 'Sealed') & (InventoryItem.card_type != 'Graded') | (InventoryItem.card_type == None))
            
        # Sorting & Filtering
        sort_choice = self.sort_var.get()
        if sort_choice == "Missing Image":
            base_query = base_query.filter((InventoryItem.image_url == None) | (InventoryItem.image_url == ""))
            base_query = base_query.order_by(InventoryItem.date_added.desc())
        elif sort_choice == "Price (High-Low)":
            base_query = base_query.order_by(InventoryItem.price.desc())
        elif sort_choice == "Price (Low-High)":
            base_query = base_query.order_by(InventoryItem.price.asc())
        elif sort_choice == "Name (A-Z)":
            base_query = base_query.order_by(InventoryItem.name.asc())
        elif sort_choice == "Set (A-Z)":
            base_query = base_query.order_by(InventoryItem.set_name.asc())
        else: # "Newest First"
            base_query = base_query.order_by(InventoryItem.date_added.desc())
            
        # Get counts BEFORE pagination
        all_items = base_query.all()
        total_items_count = sum(i.stock for i in all_items)
        total_value = sum(i.stock * i.price for i in all_items)
        total_unique_items = len(all_items)
        
        self.count_lbl.configure(text=f"TOTAL ITEMS: {total_items_count}")
        self.value_lbl.configure(text=f"TOTAL VALUE: ${total_value:,.2f}")
        
        # Pagination
        import math
        total_pages = math.ceil(total_unique_items / self.page_size) if total_unique_items > 0 else 1
        
        if self.current_page > total_pages:
            self.current_page = total_pages
            
        self.page_lbl.configure(text=f"Page {self.current_page} of {total_pages}")
        
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages else "disabled")
        
        items = base_query.offset((self.current_page - 1) * self.page_size).limit(self.page_size).all()

        from database import SyncOutbox
        outbox_skus = {row.sku for row in db_session.query(SyncOutbox.sku).filter(SyncOutbox.sync_status == 'pending').all()}

        # Check if we should show the Approve All Images button
        has_unlocked = False
        if all_items:
            has_unlocked = db_session.query(InventoryItem).filter(InventoryItem.image_locked == False).first() is not None
        
        if has_unlocked:
            self.approve_all_btn.grid()
        else:
            self.approve_all_btn.grid_remove()
            
        if active_tab == "Needs Restickering" and all_items:
            self.mark_all_restickered_btn.grid()
        else:
            self.mark_all_restickered_btn.grid_remove()

        if active_tab == "Updated Cards" and all_items:
            self.approve_under_5_btn.grid()
        else:
            self.approve_under_5_btn.grid_remove()

        import os
        base_path = os.path.dirname(__file__)
        has_missing_qr = False
        for i in all_items:
            if not os.path.exists(os.path.join(base_path, 'static', 'barcodes', f"{i.sku}.png")):
                has_missing_qr = True
                break
                
        if has_missing_qr:
            self.generate_all_qr_btn.grid()
        else:
            self.generate_all_qr_btn.grid_remove()

        app = self.winfo_toplevel()
        is_mobile = getattr(app, 'mobile_mode', False)

        if is_mobile:
            self.list_frame.configure(label_text="VAULT INVENTORY (MOBILE)")
            # Configure list_frame for 2 columns grid
            self.list_frame.grid_columnconfigure((0,1), weight=1, uniform="col")
            # Clear column configurations for columns 2 to 7
            for col in range(2, 8):
                self.list_frame.grid_columnconfigure(col, weight=0)
            
            for idx, item in enumerate(items):
                # Calculate row and column
                row_idx = idx // 2
                col_idx = idx % 2
                
                # Card Frame
                card = ctk.CTkFrame(self.list_frame, fg_color="#1A1A1A", border_width=1, border_color="#2D2D2D", corner_radius=8)
                card.grid(row=row_idx, column=col_idx, padx=8, pady=8, sticky="nsew")
                
                # Image
                thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
                if os.path.exists(thumb_path):
                    img = Image.open(thumb_path)
                    # Resize to fit nice proportions on mobile
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 168))
                    img_lbl = ctk.CTkLabel(card, image=ctk_img, text="")
                    img_lbl.pack(pady=(10, 5))
                    img_lbl.bind("<Button-1>", lambda e, i=item: self.show_details(i))
                else:
                    # Placeholder if no image exists
                    placeholder_lbl = ctk.CTkLabel(card, text="[No Image]", font=ctk.CTkFont(size=12), text_color="#8E8E8E", width=120, height=168)
                    placeholder_lbl.pack(pady=(10, 5))
                    placeholder_lbl.bind("<Button-1>", lambda e, i=item: self.show_details(i))
                
                # Price Label
                price_lbl = ctk.CTkLabel(card, text=f"${item.price:.2f}", font=ctk.CTkFont(weight="bold", size=14), text_color="#2fa572")
                price_lbl.pack(pady=(2, 5))
                price_lbl.bind("<Button-1>", lambda e, i=item: self.show_details(i))

                # Sync Status Color Logic
                is_pending = item.sku in outbox_skus
                is_synced = not is_pending and (item.sync_status in ('active', 'synced'))
                if is_pending:
                    name_color = "#EAB308"
                elif is_synced:
                    name_color = "#22C55E"
                else:
                    name_color = "#FFFFFF"

                # Name Label (Truncated/Small)
                display_name = item.name if len(item.name) <= 22 else item.name[:20] + "..."
                name_lbl = ctk.CTkLabel(card, text=display_name, font=ctk.CTkFont(size=11), text_color=name_color)
                name_lbl.pack(pady=(0, 10))
                name_lbl.bind("<Button-1>", lambda e, i=item: self.show_details(i))

                # Make the card frame itself clickable
                card.bind("<Button-1>", lambda e, i=item: self.show_details(i))
        else:
            self.list_frame.configure(label_text="ACTIVE VAULT INVENTORY (STOCK > 0)")
            self.list_frame.grid_columnconfigure(0, weight=0, minsize=90) # Image/SKU
            self.list_frame.grid_columnconfigure(1, weight=0, minsize=70) # Game
            self.list_frame.grid_columnconfigure(2, weight=0, minsize=70) # QR Code
            self.list_frame.grid_columnconfigure(3, weight=1, minsize=150) # Name
            self.list_frame.grid_columnconfigure(4, weight=1, minsize=100) # Set
            self.list_frame.grid_columnconfigure((5,6,7,8,9,10,11,12,13,14), weight=0, minsize=60)
            
            headers = ["Card", "Game", "QR Code", "Name", "Set", "Set Number", "Condition", "Quantity", "Price Paid"]
            if active_tab == "Updated Cards":
                headers.extend(["Old Price", "Updated Price"])
                self.list_frame.grid_columnconfigure(11, weight=0, minsize=60)
                self.list_frame.grid_columnconfigure(12, weight=0, minsize=60)
                self.list_frame.grid_columnconfigure(13, weight=0, minsize=60)
                self.list_frame.grid_columnconfigure(14, weight=0, minsize=60)
            else:
                headers.append("Market Price")
            headers.append("Sticker Price")
            headers.extend(["Store", "Actions"])
            for i, h in enumerate(headers): ctk.CTkLabel(self.list_frame, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=i, padx=5, sticky="w")
            for idx, item in enumerate(items, 1):
                # Thumbnail / SKU Column (Col 0)
                thumb_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
                thumb_frame.grid(row=idx, column=0, padx=10, pady=10)
                
                thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
                img = None
                
                # Placeholder Label
                img_lbl = ctk.CTkLabel(thumb_frame, text="LOADING", font=ctk.CTkFont(size=10), text_color="#8E8E8E", width=80, height=112)
                img_lbl.pack(pady=(0, 2))
                img_lbl.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))
                
                if os.path.exists(thumb_path):
                    try:
                        img = Image.open(thumb_path)
                        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 112))
                        img_lbl.configure(image=ctk_img, text="")
                        img_lbl.image = ctk_img
                    except Exception:
                        img_lbl.configure(text="[No Image]")
                else:
                    img_lbl.configure(text="[No Image]")
                
                # SKU under image
                lbl_sku = ctk.CTkLabel(thumb_frame, text=item.sku, font=ctk.CTkFont(size=11, weight="bold"), text_color="#b3b3b3")
                lbl_sku.pack()
                lbl_sku.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))
                
                # Link Image Action
                link_btn = ctk.CTkButton(thumb_frame, text="🔗 URL", width=60, height=20, font=ctk.CTkFont(size=10), fg_color="#3b8ed0", hover_color="#2c6a9b", command=lambda i=item: self.manual_link_image(i))
                link_btn.pack(pady=(2, 0))
                
                local_btn = ctk.CTkButton(thumb_frame, text="🗄️ Local DB", width=60, height=20, font=ctk.CTkFont(size=10), fg_color="#F59E0B", hover_color="#D97706", command=lambda i=item: self.fetch_local_db_image(i))
                local_btn.pack(pady=(2, 0))

                # Col 1: Game
                game_color = "#3b8ed0" if getattr(item, 'game', 'Pokemon') == 'Pokemon' else "#E11D48"
                lbl_game = ctk.CTkLabel(self.list_frame, text=getattr(item, 'game', 'Pokemon'), font=ctk.CTkFont(size=12, weight="bold"), text_color=game_color)
                lbl_game.grid(row=idx, column=1, padx=5, sticky="w")
                lbl_game.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Col 2: QR Code
                qr_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
                qr_frame.grid(row=idx, column=2, padx=5, pady=5)
                
                # FIX PATH for QR
                qr_path = os.path.join(os.path.dirname(__file__), 'static', 'barcodes', f"{item.sku}.png")
                
                qr_lbl = ctk.CTkLabel(qr_frame, text="")
                
                def load_qr(lbl=qr_lbl, path=qr_path, i=item, frame=qr_frame):
                    if not os.path.exists(path):
                        from logic import generate_item_barcode
                        generate_item_barcode(i.sku, market_price=i.price, format="QR")
                    try:
                        for w in frame.winfo_children():
                            if isinstance(w, ctk.CTkButton):
                                w.destroy()
                        img = Image.open(path)
                        c = ctk.CTkImage(light_image=img, dark_image=img, size=(45, 45))
                        lbl.configure(image=c, text="")
                        lbl.image = c
                    except:
                        lbl.configure(text="[Error]")
                
                qr_lbl.pack()
                if os.path.exists(qr_path):
                    load_qr()
                else:
                    ctk.CTkButton(qr_frame, text="Generate", width=50, font=ctk.CTkFont(size=10), command=load_qr).pack()

                # Sync Status Color Logic
                is_pending = item.sku in outbox_skus
                is_synced = not is_pending and (item.sync_status in ('active', 'synced'))
                if is_pending:
                    name_color = "#EAB308"
                elif is_synced:
                    name_color = "#22C55E"
                else:
                    name_color = "default" # Use theme default for text

                # Col 2: Name
                kwargs = {"text_color": name_color} if name_color != "default" else {}
                lbl_name = ctk.CTkLabel(self.list_frame, text=item.name, font=ctk.CTkFont(size=14, weight="bold"), **kwargs)
                lbl_name.grid(row=idx, column=3, padx=10, sticky="w")
                lbl_name.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Col 3: Set
                lbl_set = ctk.CTkLabel(self.list_frame, text=item.set_name)
                lbl_set.grid(row=idx, column=4, padx=5, sticky="w")
                lbl_set.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Col 4: Set Number
                lbl_num = ctk.CTkLabel(self.list_frame, text=item.sequence_number)
                lbl_num.grid(row=idx, column=5, padx=5, sticky="w")
                lbl_num.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Col 5: Condition
                lbl_cond = ctk.CTkLabel(self.list_frame, text=item.condition)
                lbl_cond.grid(row=idx, column=6, padx=5, sticky="w")
                lbl_cond.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Col 6: Quantity (Stock)
                e_stock = ctk.CTkEntry(self.list_frame, width=60, border_color="#333333")
                e_stock.insert(0, str(item.stock))
                e_stock.grid(row=idx, column=7, padx=5, sticky="w")
                e_stock.bind("<Return>", lambda e, i=item: self.quick_update_stock(i, e.widget.get()))

                # Col 7: Price Paid
                lbl_cost = ctk.CTkLabel(self.list_frame, text=f"${item.cost:.2f}")
                lbl_cost.grid(row=idx, column=8, padx=5, sticky="w")
                lbl_cost.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                col_offset = 0
                if active_tab == "Updated Cards":
                    old_p = getattr(item, 'old_price', None)
                    old_p_val = old_p if old_p is not None else item.price
                    lbl_old = ctk.CTkLabel(self.list_frame, text=f"${old_p_val:.2f}", text_color="#EAB308", font=ctk.CTkFont(weight="bold"))
                    lbl_old.grid(row=idx, column=9, padx=5, sticky="w")
                    col_offset = 1

                # Market Price / Updated Price
                if active_tab == "Needs Restickering" and getattr(item, 'sticker_price', None) is not None:
                    current_p = float(round(item.price if item.price is not None else 0.0))
                    price_text = f"${item.sticker_price:.2f} ➔ ${current_p:.2f}"
                else:
                    price_text = f"${item.price:.2f}"
                    
                lbl_price = ctk.CTkLabel(self.list_frame, text=price_text, text_color="#2fa572", font=ctk.CTkFont(weight="bold"))
                lbl_price.grid(row=idx, column=9 + col_offset, padx=5, sticky="w")
                lbl_price.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Sticker Price
                sp = getattr(item, 'sticker_price', None)
                if sp is None:
                    sp = float(item.price if item.price is not None else 0.0)
                lbl_sp = ctk.CTkLabel(self.list_frame, text=f"${sp:.2f}", text_color="#3b8ed0", font=ctk.CTkFont(weight="bold"))
                lbl_sp.grid(row=idx, column=10 + col_offset, padx=5, sticky="w")
                lbl_sp.bind("<Double-Button-1>", lambda e, i=item: self.show_details(i))

                # Store Live/Paused Toggle
                is_live = item.sync_status in ('active', 'synced', 'approved')
                store_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
                store_frame.grid(row=idx, column=11 + col_offset, padx=5, sticky="w")

                store_switch = ctk.CTkSwitch(
                    store_frame,
                    text="Live" if is_live else "Paused",
                    width=70,
                    progress_color="#10B981",
                    button_color="#FFFFFF",
                    font=ctk.CTkFont(size=11)
                )
                if is_live:
                    store_switch.select()
                else:
                    store_switch.deselect()
                store_switch.pack(pady=(0, 4))

                qty_var = tk.IntVar(value=max(0, item.stock - (getattr(item, 'paused_stock', 0) or 0)))

                if item.stock > 1:
                    smart_sub_frame = ctk.CTkFrame(store_frame, fg_color="#27272A", corner_radius=6)
                    smart_sub_frame.pack(fill="x")
                    
                    lbl_status = ctk.CTkLabel(smart_sub_frame, text=f"{qty_var.get()} Live | {item.stock - qty_var.get()} Paused", font=ctk.CTkFont(size=10, weight="bold"), text_color="#F59E0B" if (item.stock - qty_var.get()) > 0 else "#10B981")
                    lbl_status.pack(pady=(2, 2))
                    
                    btn_sub_frame = ctk.CTkFrame(smart_sub_frame, fg_color="transparent")
                    btn_sub_frame.pack(pady=(0, 4))
                    
                    def dec_qty(qv=qty_var, tot=item.stock, lbl=lbl_status, it=item):
                        if qv.get() > 0:
                            qv.set(qv.get() - 1)
                            paused = tot - qv.get()
                            it.paused_stock = paused
                            lbl.configure(text=f"{qv.get()} Live | {paused} Paused", text_color="#F59E0B" if paused > 0 else "#10B981")
                            from database import SyncOutbox
                            from logic import calculate_shop_price
                            calc_price = calculate_shop_price(it.price) if not getattr(it, 'shop_listing_price', None) else it.shop_listing_price
                            outbox = SyncOutbox(action_type='stock_update', sku=it.sku, quantity_change=qv.get(), new_price=calc_price)
                            db_session.add(outbox)
                            db_session.commit()
                            
                    def inc_qty(qv=qty_var, tot=item.stock, lbl=lbl_status, it=item):
                        if qv.get() < tot:
                            qv.set(qv.get() + 1)
                            paused = tot - qv.get()
                            it.paused_stock = paused
                            lbl.configure(text=f"{qv.get()} Live | {paused} Paused", text_color="#F59E0B" if paused > 0 else "#10B981")
                            from database import SyncOutbox
                            from logic import calculate_shop_price
                            calc_price = calculate_shop_price(it.price) if not getattr(it, 'shop_listing_price', None) else it.shop_listing_price
                            outbox = SyncOutbox(action_type='stock_update', sku=it.sku, quantity_change=qv.get(), new_price=calc_price)
                            db_session.add(outbox)
                            db_session.commit()
                            
                    ctk.CTkButton(btn_sub_frame, text="➖", width=24, height=20, fg_color="#374151", hover_color="#1F2937", command=dec_qty).pack(side="left", padx=2)
                    ctk.CTkButton(btn_sub_frame, text="➕", width=24, height=20, fg_color="#374151", hover_color="#1F2937", command=inc_qty).pack(side="left", padx=2)

                    def on_store_toggle(sw=store_switch, i=item, qv=qty_var, tot=item.stock, lbl=lbl_status):
                        from database import SyncOutbox
                        from logic import calculate_shop_price
                        calc_price = calculate_shop_price(i.price) if not getattr(i, 'shop_listing_price', None) else i.shop_listing_price
                        if sw.get():
                            sw.configure(text="Live")
                            i.sync_status = 'approved'
                            if qv.get() == 0:
                                qv.set(tot)
                                i.paused_stock = 0
                            outbox = SyncOutbox(action_type='stock_update', sku=i.sku, quantity_change=qv.get(), new_price=calc_price)
                            db_session.add(outbox)
                            db_session.commit()
                        else:
                            sw.configure(text="Paused")
                            was_synced = i.sync_status in ('active', 'synced', 'approved')
                            i.sync_status = 'paused'
                            qv.set(0)
                            i.paused_stock = tot
                            db_session.commit()
                            if was_synced:
                                outbox = SyncOutbox(action_type='stock_update', sku=i.sku, quantity_change=0, new_price=0.0)
                                db_session.add(outbox)
                                db_session.commit()
                        paused = tot - qv.get()
                        lbl.configure(text=f"{qv.get()} Live | {paused} Paused", text_color="#F59E0B" if paused > 0 else "#10B981")

                    store_switch.configure(command=on_store_toggle)
                else:
                    def on_store_toggle(sw=store_switch, i=item):
                        if sw.get():
                            sw.configure(text="Live")
                            i.sync_status = 'approved'
                            i.paused_stock = 0
                            from database import SyncOutbox
                            from logic import calculate_shop_price
                            calc_price = calculate_shop_price(i.price) if not getattr(i, 'shop_listing_price', None) else i.shop_listing_price
                            outbox = SyncOutbox(action_type='stock_update', sku=i.sku, quantity_change=i.stock, new_price=calc_price)
                            db_session.add(outbox)
                            db_session.commit()
                        else:
                            sw.configure(text="Paused")
                            was_synced = i.sync_status in ('active', 'synced', 'approved')
                            i.sync_status = 'paused'
                            i.paused_stock = 1
                            db_session.commit()
                            if was_synced:
                                from database import SyncOutbox
                                outbox = SyncOutbox(action_type='stock_update', sku=i.sku, quantity_change=0, new_price=0.0)
                                db_session.add(outbox)
                                db_session.commit()

                    store_switch.configure(command=on_store_toggle)

                # Actions Frame
                action_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
                action_frame.grid(row=idx, column=12 + col_offset, padx=5, sticky="w")
                
                if active_tab == "Updated Cards" or item.needs_update:
                    ctk.CTkButton(action_frame, text="✅", fg_color="#2fa572", width=30, hover_color="#268a5f",
                                  command=lambda i=item: self.approve_resticker(i)).pack(side="left", padx=(0, 5))
                elif active_tab == "Needs Restickering":
                    ctk.CTkButton(action_frame, text="✅", fg_color="#2fa572", width=30, hover_color="#268a5f",
                                  command=lambda i=item: self.approve_physical_resticker(i)).pack(side="left", padx=(0, 5))
                
                if active_tab == "Updated Cards":
                    ctk.CTkButton(action_frame, text="❌", fg_color="#944747", width=30, hover_color="#7A3B3B",
                                  command=lambda i=item: self.ignore_price_change(i)).pack(side="left", padx=(0, 5))
                else:
                    # Void Action
                    ctk.CTkButton(action_frame, text="❌", fg_color="#944747", width=30, hover_color="#7A3B3B",
                                  command=lambda i=item: self.void_item(i)).pack(side="left", padx=(0, 5))
                              
                # Label Action
                ctk.CTkButton(action_frame, text="🏷️", width=30,
                              command=lambda i=item: self.show_label_options(i)).pack(side="left", padx=(0, 5))
                              
                # Price Edit Action
                ctk.CTkButton(action_frame, text="💲", fg_color="#F59E0B", width=30, hover_color="#D97706",
                              command=lambda i=item: self.manual_edit_price(i)).pack(side="left", padx=(0, 5))

    def ignore_price_change(self, item):
        from database import db_session
        if getattr(item, 'old_price', None) is not None:
            item.price = item.old_price
            
            from logic import calculate_shop_listing_price, calculate_suggested_price
            from database import SyncOutbox, SystemSettings
            
            settings = db_session.query(SystemSettings).first()
            rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
            
            item.sticker_price = calculate_suggested_price(item.price, rule=rounding_rule)
            shop_price = calculate_shop_listing_price(item.price, item.card_type)
            item.shop_listing_price = shop_price
            
            outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
            db_session.add(outbox)
            
        item.needs_update = False
        db_session.commit()
        self.refresh_list()

    def manual_edit_price(self, item):
        from tkinter import messagebox
        dialog = ctk.CTkInputDialog(text=f"Enter new price for '{item.name}':\n(Current: ${item.price:.2f})", title="Quick Edit Price")
        new_val = dialog.get_input()
        if new_val:
            try:
                new_price = float(new_val.replace('$', '').replace(',', ''))
                old_price = item.price
                if abs(old_price - new_price) > 0.001:
                    item.price = new_price
                    from logic import calculate_shop_listing_price, calculate_suggested_price
                    from database import SystemSettings, SyncOutbox
                    settings = db_session.query(SystemSettings).first()
                    rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
                    
                    item.sticker_price = calculate_suggested_price(new_price, rule=rounding_rule)
                    shop_price = calculate_shop_listing_price(new_price, item.card_type)
                    item.shop_listing_price = shop_price  # Explicitly save so we don't push old prices later
                    
                    outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
                    db_session.add(outbox)
                    db_session.commit()
                    self.refresh_list()
                    if self.refresh_callback:
                        self.refresh_callback()
            except ValueError:
                messagebox.showerror("Error", "Invalid price format.")

    def approve_physical_resticker(self, item):
        from logic import calculate_suggested_price
        from database import SystemSettings
        settings = db_session.query(SystemSettings).first()
        rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
        item.sticker_price = calculate_suggested_price(item.price if item.price is not None else 0.0, rule=rounding_rule)
        db_session.commit()
        self.refresh_list()

    def run_mark_all_restickered(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Mark All Restickered", "This will mark ALL currently filtered items as Restickered.\n\nProceed?"):
            return
        
        try:
            # We must fetch the current filtered items.
            query = self.search_entry.get().lower()
            base_query = db_session.query(InventoryItem).filter(
                (InventoryItem.name.ilike(f"%{query}%")) | (InventoryItem.sku.ilike(f"%{query}%")) | (InventoryItem.set_name.ilike(f"%{query}%"))
            ).filter(InventoryItem.stock > 0)
            
            from sqlalchemy import func
            from database import SystemSettings
            settings = db_session.query(SystemSettings).first()
            threshold = settings.resticker_threshold if settings and settings.resticker_threshold is not None else 2.00
            import math
            base_query = base_query.filter(InventoryItem.sticker_price.isnot(None), func.abs(InventoryItem.sticker_price - func.ceil(InventoryItem.price)) >= threshold)
            
            items = base_query.all()
            from logic import calculate_suggested_price
            rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
            for item in items:
                item.sticker_price = calculate_suggested_price(item.price if item.price is not None else 0.0, rule=rounding_rule)
            db_session.commit()
            messagebox.showinfo("Success", f"Marked {len(items)} items as restickered!")
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to mark all restickered: {e}")

    def run_approve_under_5(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Accept < $5 Changes", "This will automatically accept all price updates where the absolute price change is under $5.00.\n\nProceed?"):
            return
            
        try:
            from database import db_session, InventoryItem, SyncOutbox
            from logic import calculate_shop_price
            
            # Fetch all items needing update
            query = self.search_entry.get().lower()
            base_query = db_session.query(InventoryItem).filter(
                (InventoryItem.name.ilike(f"%{query}%")) | (InventoryItem.sku.ilike(f"%{query}%")) | (InventoryItem.set_name.ilike(f"%{query}%"))
            ).filter(InventoryItem.needs_update == True)
            
            items = base_query.all()
            approved_count = 0
            for item in items:
                old_p = item.old_price if item.old_price is not None else 0.0
                curr_p = item.price if item.price is not None else 0.0
                if abs(curr_p - old_p) < 5.00:
                    item.needs_update = False
                    shop_price = getattr(item, 'shop_listing_price', None)
                    if not shop_price:
                        shop_price = calculate_shop_price(curr_p)
                        item.shop_listing_price = shop_price
                    outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
                    db_session.add(outbox)
                    approved_count += 1
            
            if approved_count > 0:
                db_session.commit()
                messagebox.showinfo("Success", f"Automatically accepted {approved_count} price changes under $5.00!")
                self.refresh_list()
            else:
                messagebox.showinfo("No Matches", "No pending price updates were found with a change under $5.00.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to accept price changes: {e}")

    def approve_resticker(self, item):
        item.needs_update = False
        from database import db_session, SyncOutbox
        from logic import calculate_shop_price
        shop_price = getattr(item, 'shop_listing_price', None)
        if not shop_price:
            shop_price = calculate_shop_price(item.price)
            item.shop_listing_price = shop_price
        outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
        db_session.add(outbox)
        db_session.commit()
        self.refresh_list()

    def manual_link_image(self, item):
        dialog = ctk.CTkInputDialog(text=f"Paste image URL for '{item.name}':", title="Manual Image Link")
        url = dialog.get_input()
        if url and url.strip():
            # Delete old thumbnail if it exists to force refresh
            import os
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
            if os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                except Exception:
                    pass
                    
            item.image_url = url.strip()
            item.image_locked = True # Auto-lock manual edits
            db_session.commit()
            
            # Immediately download the image so it displays in the UI
            import requests
            try:
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                r = requests.get(item.image_url, timeout=5)
                if r.status_code == 200:
                    with open(thumb_path, 'wb') as f:
                        f.write(r.content)
            except Exception as e:
                print(f"Failed to download pasted image: {e}")
                
            self.refresh_list()

    def fetch_local_db_image(self, item):
        import sys, os, shutil
        img_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image_db_manager')
        if img_db_path not in sys.path:
            sys.path.append(img_db_path)
        import db_handler as img_db_handler

        local_img = img_db_handler.find_image_by_set_and_number(item.set_name, item.sequence_number, card_name=item.name)
        if local_img and os.path.exists(local_img):
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            if os.path.exists(thumb_path):
                try: os.remove(thumb_path)
                except: pass
            
            try:
                shutil.copyfile(local_img, thumb_path)
                item.image_url = thumb_path
                item.custom_image_url = thumb_path
                db_session.commit()
                self.refresh_list()
                from tkinter import messagebox
                messagebox.showinfo("Success", "Loaded image from Local DB.")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Error", f"Failed to copy image: {e}")
        else:
            from tkinter import messagebox
            messagebox.showwarning("Not Found", "Could not find a local DB image for this card.")

    def show_label_options(self, item):
        popup = ctk.CTkToplevel(self)
        popup.title(f"Label: {item.sku}")
        popup.geometry("300x150")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        
        lbl = ctk.CTkLabel(popup, text=f"Generate Label for {item.sku}", font=ctk.CTkFont(weight="bold"))
        lbl.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        def do_copy(format_type):
            from logic import generate_item_barcode, copy_barcode_to_clipboard
            generate_item_barcode(item.sku, market_price=item.price, format=format_type)
            success = copy_barcode_to_clipboard(item.sku)
            if success:
                lbl.configure(text="Copied!", text_color="#2fa572")
                self.after(1500, popup.destroy)
            else:
                lbl.configure(text="Copy failed.", text_color="#944747")
                
        ctk.CTkButton(btn_frame, text="Copy Barcode", command=lambda: do_copy("Barcode")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Copy QR Code", command=lambda: do_copy("QR")).pack(side="left", padx=5)

    def quick_update_stock(self, item, new_val):
        try:
            new_stock = int(new_val)
            diff = new_stock - item.stock
            if diff != 0:
                item.stock = new_stock
                from database import SyncOutbox
                outbox = SyncOutbox(action_type='stock_update', sku=item.sku, quantity_change=diff, new_price=0.0)
                db_session.add(outbox)
                db_session.commit()
                self.refresh_list()
                self.refresh_callback() # Updates dashboard
                print(f"[*] Quick Update: SKU {item.sku} stock set to {item.stock} (Sync queued: {diff})")
        except ValueError:
            messagebox.showerror("Error", "Stock must be an integer.")
        except Exception as e:
            db_session.rollback()
            messagebox.showerror("Error", f"Failed to update stock: {e}")

    def show_details(self, item):
        app = self.winfo_toplevel()
        app.show_overlay(InventoryItemDetailView, title=f"VAULT DETAIL: {item.name}", item=item)

    def void_item(self, item):
        if messagebox.askyesno("Confirm Void", f"Permanently remove all stock for {item.name} ({item.sku})?"):
            try:
                diff = 0 - item.stock
                if diff != 0:
                    from database import SyncOutbox
                    outbox = SyncOutbox(action_type='stock_update', sku=item.sku, quantity_change=diff, new_price=0.0)
                    db_session.add(outbox)
                # Set stock to 0 instead of deleting to keep history data
                item.stock = 0
                db_session.commit()
                self.refresh_list()
                self.refresh_callback()
            except Exception as e:
                db_session.rollback()
                messagebox.showerror("Error", f"Failed to void item: {e}")

class UpdatedCardsFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.count_lbl = ctk.CTkLabel(self.header_frame, text="UPDATED CARDS: 0", font=ctk.CTkFont(weight="bold"))
        self.count_lbl.pack(side="left", padx=10)

        # List
        self.list_frame = ctk.CTkScrollableFrame(self, label_text="CARDS REQUIRING RESTICKERING")
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.list_frame.grid_columnconfigure((0,1,2,3,4,5), weight=1, uniform=False)

        self.refresh_list()

    def refresh_list(self):
        for child in self.list_frame.winfo_children(): child.destroy()
        
        items = db_session.query(InventoryItem).filter(InventoryItem.needs_update == True).all()
        self.count_lbl.configure(text=f"UPDATED CARDS: {len(items)}")
        
        headers = ["Image", "SKU", "Item Name", "Previous Price", "New Price", "Actions", "Mark Restickered"]
        for i, h in enumerate(headers): ctk.CTkLabel(self.list_frame, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=i, padx=5, sticky="w")
        
        for idx, item in enumerate(items, 1):
            # Thumbnail Column
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
            if os.path.exists(thumb_path):
                img = Image.open(thumb_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 56))
                img_lbl = ctk.CTkLabel(self.list_frame, image=ctk_img, text="")
                img_lbl.grid(row=idx, column=0, padx=5, pady=2)
            else:
                ctk.CTkLabel(self.list_frame, text="No Img").grid(row=idx, column=0, padx=5, pady=2)
            
            # SKU
            ctk.CTkLabel(self.list_frame, text=item.sku).grid(row=idx, column=1, padx=5, sticky="w")
            
            # Name
            ctk.CTkLabel(self.list_frame, text=item.name).grid(row=idx, column=2, padx=5, sticky="w")
            
            # Prices
            old_p = item.old_price if getattr(item, 'old_price', None) is not None else 0.0
            ctk.CTkLabel(self.list_frame, text=f"${old_p:.2f}", font=ctk.CTkFont(weight="bold")).grid(row=idx, column=3, padx=5, sticky="w")
            ctk.CTkLabel(self.list_frame, text=f"${item.price:.2f}", font=ctk.CTkFont(weight="bold"), text_color="#2fa572").grid(row=idx, column=4, padx=5, sticky="w")
            
            # Label Action
            ctk.CTkButton(self.list_frame, text="🏷️ Label", width=60, command=lambda i=item: self.show_label_options(i)).grid(row=idx, column=5, padx=5, sticky="w")
            
            # Mark Restickered
            ctk.CTkButton(self.list_frame, text="✅ Restickered", width=100, fg_color="#2fa572", hover_color="#237a54", command=lambda i=item: self.mark_restickered(i)).grid(row=idx, column=6, padx=5, sticky="w")


    def show_label_options(self, item):
        popup = ctk.CTkToplevel(self)
        popup.title(f"Label: {item.sku}")
        popup.geometry("300x150")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        
        lbl = ctk.CTkLabel(popup, text=f"Generate Label for {item.sku}", font=ctk.CTkFont(weight="bold"))
        lbl.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        def do_copy(format_type):
            from logic import generate_item_barcode, copy_barcode_to_clipboard
            generate_item_barcode(item.sku, market_price=item.price, format=format_type)
            success = copy_barcode_to_clipboard(item.sku)
            if success:
                lbl.configure(text="Copied!", text_color="#2fa572")
                self.after(1500, popup.destroy)
            else:
                lbl.configure(text="Copy failed.", text_color="#944747")
                
        ctk.CTkButton(btn_frame, text="Copy Barcode", command=lambda: do_copy("Barcode")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Copy QR Code", command=lambda: do_copy("QR")).pack(side="left", padx=5)

    def mark_restickered(self, item):
        try:
            item.needs_update = False
            db_session.commit()
            self.refresh_list()
        except Exception as e:
            db_session.rollback()
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to mark as restickered: {e}")

class DatabaseResetDialog(ctk.CTkToplevel):
    def __init__(self, master, confirm_callback):
        super().__init__(master)
        self.title("Database Reset Confirmation")
        self.geometry("450x270")
        self.attributes("-topmost", True)
        self.grab_set()
        
        self.confirm_callback = confirm_callback
        
        ctk.CTkLabel(self, text="⚠️ FINAL WARNING", text_color="#EF4444", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="To confirm the permanent deletion of your data,\nplease type 'DELETE' in the box below.", font=("Segoe UI", 12)).pack(pady=5)
        
        self.entry_var = tk.StringVar()
        self.entry_var.trace_add("write", self.validate_input)
        self.entry = ctk.CTkEntry(self, textvariable=self.entry_var, width=150, justify="center", border_color="#333333")
        self.entry.pack(pady=10)
        
        self.include_purchases_var = ctk.BooleanVar(value=False)
        self.purchases_checkbox = ctk.CTkCheckBox(self, text="Also delete all Purchase Records", variable=self.include_purchases_var, text_color="#EF4444", fg_color="#F2A900", hover_color="#C88A00")
        self.purchases_checkbox.pack(pady=5)
        
        self.confirm_btn = ctk.CTkButton(self, text="Confirm Wipe", fg_color="#B91C1C", hover_color="#991B1B", state="disabled", command=self.on_confirm)
        self.confirm_btn.pack(pady=15)
        
    def validate_input(self, *args):
        if self.entry_var.get().strip() == "DELETE":
            self.confirm_btn.configure(state="normal")
        else:
            self.confirm_btn.configure(state="disabled")
            
    def on_confirm(self):
        include_purchases = self.include_purchases_var.get()
        self.destroy()
        self.confirm_callback(include_purchases)

class SetNamesDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Manage OCR Set Names")
        self.geometry("600x700")
        
        # Center the window relative to parent
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Tabview row expands
        
        # Header
        ctk.CTkLabel(self, text="OCR Set Names Dictionary", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=15)
        
        # Description
        desc = ("Enter one set name per line. When OCR attempts to match a set name, "
                "it will compare the scanned text against these lists and choose the closest "
                "match. Keep spelling precise.")
        ctk.CTkLabel(self, text=desc, font=ctk.CTkFont(size=11), text_color="#A0A0A0", wraplength=550, justify="left").grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        
        # Tabview for languages
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        self.tabview.add("English")
        self.tabview.add("Japanese")
        self.tabview.add("Chinese")
        
        # Text Boxes for each tab
        self.textboxes = {}
        for lang in ["English", "Japanese", "Chinese"]:
            tb = ctk.CTkTextbox(self.tabview.tab(lang), font=ctk.CTkFont(family="Consolas", size=12))
            tb.pack(fill="both", expand=True, padx=5, pady=5)
            self.textboxes[lang] = tb
            
        # Define paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.file_paths = {
            "English": os.path.join(base_dir, 'set_names.txt'),
            "Japanese": os.path.join(base_dir, 'set_names_ja.txt'),
            "Chinese": os.path.join(base_dir, 'set_names_zh.txt')
        }
        
        self.load_sets()
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=15, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="#444444", command=self.destroy).grid(row=0, column=0, padx=10, pady=5, sticky="e")
        ctk.CTkButton(btn_frame, text="💾 Save Changes", fg_color="#2fa572", command=self.save_sets).grid(row=0, column=1, padx=10, pady=5, sticky="w")

    def load_sets(self):
        for lang, path in self.file_paths.items():
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.textboxes[lang].insert("1.0", content)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load {lang} set names: {e}")
            else:
                self.textboxes[lang].insert("1.0", "")

    def save_sets(self):
        saved_counts = []
        try:
            for lang, path in self.file_paths.items():
                content = self.textboxes[lang].get("1.0", tk.END)
                lines = [line.strip() for line in content.split('\n')]
                cleaned_lines = []
                seen = set()
                for line in lines:
                    if line and not line.startswith('#'):
                        line_lower = line.lower()
                        if line_lower not in seen:
                            seen.add(line_lower)
                            cleaned_lines.append(line)
                
                cleaned_lines.sort()
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(cleaned_lines) + '\n')
                saved_counts.append(f"{lang}: {len(cleaned_lines)}")
            
            messagebox.showinfo("Success", "Saved set names successfully:\n" + "\n".join(saved_counts))
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save set names: {e}")

class SettingsFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        ctk.CTkLabel(self, text="GLOBAL SYSTEM CONFIGURATIONS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=(0, 20), sticky="w")

        # 1. Main Config Card
        card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#2D2D2D", border_width=1)
        card.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        card.grid_columnconfigure(1, weight=1)

        settings = db_session.query(SystemSettings).first()
        
        # Inputs
        self.buy_entry = self.create_setting_row(card, 0, "Buy Multiplier (Cash %)", "Percentage paid for cash buy-ins", ctk.CTkEntry(card, width=150, border_color="#333333"))
        self.buy_entry.insert(0, str(settings.buy_percentage if settings else 0.70))

        self.trade_entry = self.create_setting_row(card, 1, "Trade Multiplier (Credit %)", "Multiplier for store credit", ctk.CTkEntry(card, width=150, border_color="#333333"))
        self.trade_entry.insert(0, str(settings.trade_percentage if settings else 0.80))

        self.rounding_menu = self.create_setting_row(card, 2, "Rounding Strategy", "How to normalize suggested prices", 
                                                     ctk.CTkOptionMenu(card, values=["Round Up to Nearest $1.00", "Round to Nearest $0.95 Cents", "Keep Raw TCG Decimal Payouts"], width=250, button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00"))
        self.rounding_menu.set(settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts")

        self.resticker_entry = self.create_setting_row(card, 3, "Resticker Threshold ($)", "Price diff to trigger restickering", ctk.CTkEntry(card, width=150, border_color="#333333"))
        self.resticker_entry.insert(0, str(settings.resticker_threshold if settings else 2.00))

        self.sim_switch = ctk.CTkSwitch(card, text="", onvalue=True, offvalue=False, progress_color="#F2A900")
        self.create_setting_row(card, 4, "Simulation Mode", "Bypass Shopify network calls for testing", self.sim_switch)
        if settings and settings.sim_mode:
            self.sim_switch.select()
        else:
            self.sim_switch.deselect()

        self.markup_type_menu = self.create_setting_row(card, 5, "Shopify Markup Type", "Percentage or flat dollar amount",
                                                       ctk.CTkOptionMenu(card, values=["Percentage (%)", "Flat Amount ($)"], width=200, button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00"))
        self.markup_type_menu.set(settings.markup_type if settings else "Percentage (%)")

        self.markup_val_entry = self.create_setting_row(card, 6, "Markup Value", "Amount to mark up by", ctk.CTkEntry(card, width=150, border_color="#333333"))
        self.markup_val_entry.insert(0, str(settings.markup_value if settings else 0.0))

        self.shop_rounding_menu = self.create_setting_row(card, 7, "Shopify Rounding Rule", "Apply rounding to shop price",
                                                          ctk.CTkOptionMenu(card, values=["Round to nearest .99", "Round to nearest .50", "Exact/None"], width=200, button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00"))
        self.shop_rounding_menu.set(settings.rounding_rule if settings else "Exact/None")

        self.sim_shopify_switch = ctk.CTkSwitch(card, text="", onvalue=True, offvalue=False, progress_color="#10B981", command=self.toggle_sim_shopify_button)
        self.create_setting_row(card, 8, "Show 'Simulate Shopify Purchase' Button", "Toggle simulation button at top of window", self.sim_shopify_switch)

        self.omit_graded_switch = ctk.CTkSwitch(card, text="", onvalue=True, offvalue=False, progress_color="#F2A900")
        self.create_setting_row(card, 9, "Omit Graded from Recon", "Skip graded cards during price sync", self.omit_graded_switch)
        if settings and settings.omit_graded_from_recon:
            self.omit_graded_switch.select()
        else:
            self.omit_graded_switch.deselect()
            
        # Gmail Auto-Recon Card
        gmail_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#D93025", border_width=1)
        gmail_card.grid(row=2, column=0, sticky="nsew", padx=2, pady=10)
        gmail_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(gmail_card, text="📧 GMAIL AUTO-RECON", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=15, padx=20, sticky="w")
        ctk.CTkLabel(gmail_card, text="Automatically monitor a Gmail folder for Collectr CSVs and trigger Recon.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")
        
        self.gmail_monitor_switch = ctk.CTkSwitch(gmail_card, text="", onvalue=True, offvalue=False, progress_color="#D93025", command=self.toggle_gmail_monitor)
        self.create_setting_row(gmail_card, 2, "Enable Gmail Monitoring", "Starts background daemon on launch", self.gmail_monitor_switch)
        if settings and settings.gmail_monitor_enabled:
            self.gmail_monitor_switch.select()
        else:
            self.gmail_monitor_switch.deselect()
            
        self.gmail_addr_entry = self.create_setting_row(gmail_card, 3, "Gmail Address", "e.g. yourshop@gmail.com", ctk.CTkEntry(gmail_card, width=250, border_color="#333333"))
        self.gmail_addr_entry.insert(0, str(settings.gmail_address if settings else ''))
        
        self.gmail_pass_entry = self.create_setting_row(gmail_card, 4, "App Password", "16-character Google App Password", ctk.CTkEntry(gmail_card, width=250, show="*", border_color="#333333"))
        self.gmail_pass_entry.insert(0, str(settings.gmail_app_password if settings else ''))
        
        self.gmail_folder_entry = self.create_setting_row(gmail_card, 5, "Target Folder/Label", "The label Gmail applies to CSV emails", ctk.CTkEntry(gmail_card, width=250, border_color="#333333"))
        self.gmail_folder_entry.insert(0, str(settings.gmail_folder if settings else 'INBOX'))
        
        self.test_gmail_btn = ctk.CTkButton(gmail_card, text="Test Connection", width=200, fg_color="#10B981", hover_color="#059669", command=self.test_gmail_connection)
        self.test_gmail_btn.grid(row=6, column=1, padx=20, pady=(0, 15), sticky="e")

        # 1.5. Exports Card
        exports_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#10B981", border_width=1)
        exports_card.grid(row=3, column=0, sticky="nsew", padx=2, pady=10)
        exports_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(exports_card, text="📊 DATA EXPORTS", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, pady=15, padx=20, sticky="w")
        ctk.CTkLabel(exports_card, text="Export active inventory with QR codes to Excel.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")
        
        self.export_sort_menu = ctk.CTkOptionMenu(exports_card, values=["Alphabetical (A-Z)", "Price: High to Low", "Price: Low to High", "Newest First"], width=180, button_color="#10B981", button_hover_color="#059669", dropdown_hover_color="#059669")
        self.export_sort_menu.grid(row=1, column=1, padx=(0, 10), pady=(0, 15), sticky="e")
        self.export_sort_menu.set("Alphabetical (A-Z)")
        
        self.export_btn = ctk.CTkButton(exports_card, text="Export Inventory to Excel", command=self.export_inventory_to_excel, fg_color="#10B981", hover_color="#059669", width=200)
        self.export_btn.grid(row=1, column=2, padx=20, pady=(0, 15), sticky="e")
        
        self.export_selected_btn = ctk.CTkButton(exports_card, text="Export Selected to Excel", command=self.open_export_selected_modal, fg_color="#F59E0B", hover_color="#D97706", width=200)
        self.export_selected_btn.grid(row=2, column=2, padx=20, pady=(0, 15), sticky="e")

        # 2. Database Backup Card
        sync_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#3b8ed0", border_width=1)
        sync_card.grid(row=4, column=0, sticky="nsew", padx=2, pady=20)
        sync_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(sync_card, text="💾 DATABASE BACKUP & RESTORE", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=15, padx=20, sticky="w")
        
        btn_f = ctk.CTkFrame(sync_card, fg_color="transparent")
        btn_f.grid(row=1, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_f, text="⬆️ Export Database Backup", command=self.export_db_backup, fg_color="#3b8ed0", width=250).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="⬇️ Import Database Backup", command=self.import_db_backup, fg_color="#d35400", width=250).pack(side="left", padx=10)

        # 3. OCR Set Names Management Card
        sets_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#2D2D2D", border_width=1)
        sets_card.grid(row=4, column=0, sticky="nsew", padx=2, pady=10)
        sets_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(sets_card, text="📝 OCR SET DICTIONARY", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=15, padx=20, sticky="w")
        ctk.CTkLabel(sets_card, text="Configure set names for OCR auto-correction and fuzzy matching.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")
        ctk.CTkButton(sets_card, text="⚙️ Manage Set Names", command=self.open_set_names_editor, fg_color="#3b8ed0", width=200).grid(row=1, column=1, padx=20, pady=(0, 15), sticky="e")

        # 4. Danger Zone Card
        danger_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#7F1D1D", border_width=1)
        danger_card.grid(row=5, column=0, sticky="nsew", padx=2, pady=10)
        danger_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(danger_card, text="⚠️ DANGER ZONE", text_color="#EF4444", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=15, padx=20, sticky="w")
        ctk.CTkLabel(danger_card, text="Permanently wipe all inventory, sales, and staging data from the local database.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")
        ctk.CTkButton(danger_card, text="Wipe All Inventory", command=self.on_wipe_inventory_clicked, fg_color="#B91C1C", hover_color="#991B1B", width=200).grid(row=1, column=1, padx=20, pady=(0, 15), sticky="e")

        # 5. Shipping Rules Card
        ship_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#2D2D2D", border_width=1)
        ship_card.grid(row=6, column=0, sticky="nsew", padx=2, pady=10)
        ship_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(ship_card, text="📦 SHOPIFY SHIPPING & PADDING RULES", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=15, padx=20, sticky="w")
        
        # Add rule area
        add_f = ctk.CTkFrame(ship_card, fg_color="transparent")
        add_f.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=5)
        
        ctk.CTkLabel(add_f, text="Min $").pack(side="left", padx=2)
        self.min_entry = ctk.CTkEntry(add_f, width=60, border_color="#333333")
        self.min_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(add_f, text="Max $").pack(side="left", padx=2)
        self.max_entry = ctk.CTkEntry(add_f, width=60, border_color="#333333")
        self.max_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(add_f, text="Add $").pack(side="left", padx=2)
        self.add_entry = ctk.CTkEntry(add_f, width=60, border_color="#333333")
        self.add_entry.pack(side="left", padx=2)
        
        self.type_menu = ctk.CTkOptionMenu(add_f, values=["Single", "Sealed", "Graded"], width=80, button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00")
        self.type_menu.pack(side="left", padx=10)
        
        ctk.CTkButton(add_f, text="➕ Add Rule", width=80, command=self.add_shipping_rule).pack(side="left", padx=10)
        
        self.rules_scroll = ctk.CTkScrollableFrame(ship_card, height=150, fg_color="#09090B")
        self.rules_scroll.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=15)
        
        self.refresh_shipping_rules()

        # 6. CSV Operations Card
        csv_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_color="#2D2D2D", border_width=1)
        csv_card.grid(row=7, column=0, sticky="nsew", padx=2, pady=10)
        csv_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(csv_card, text="📄 CSV OPERATIONS", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=15, padx=20, sticky="w")

        # Patch CSV row
        ctk.CTkLabel(csv_card, text="Patch conditions from a bulk CSV file.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        self.patch_btn = ctk.CTkButton(csv_card, text="🩹 Patch CSV", command=self.run_csv_patch, fg_color="#F59E0B", hover_color="#D97706", width=200)
        self.patch_btn.grid(row=1, column=1, padx=20, pady=(0, 10), sticky="e")

        # Import CSV row
        ctk.CTkLabel(csv_card, text="Full DB import from a Collectr / external CSV export.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=2, column=0, padx=20, pady=(0, 15), sticky="w")
        self.import_csv_btn = ctk.CTkButton(csv_card, text="📥 Import CSV", command=self.run_csv_import, fg_color="#10B981", hover_color="#059669", width=200)
        self.import_csv_btn.grid(row=2, column=1, padx=20, pady=(0, 15), sticky="e")

        # Validate & Fetch Images row
        ctk.CTkLabel(csv_card, text="Validate cards and fetch missing high-res images from API.", font=ctk.CTkFont(size=11), text_color="#8E8E8E").grid(row=3, column=0, padx=20, pady=(0, 15), sticky="w")
        self.fetch_images_btn = ctk.CTkButton(csv_card, text="🔍 Validate & Fetch Images", command=self.run_fetch_images, fg_color="#f39c12", hover_color="#d68910", width=200)
        self.fetch_images_btn.grid(row=3, column=1, padx=20, pady=(0, 15), sticky="e")

        # Save Button
        save_btn = ctk.CTkButton(self, text="💾 Save All Configurations", height=50, fg_color="#2fa572",
                                 font=ctk.CTkFont(weight="bold"), command=self.save_settings)
        save_btn.grid(row=8, column=0, pady=10, sticky="ew")

    def toggle_sim_shopify_button(self):
        app = self.winfo_toplevel()
        if hasattr(app, "toggle_sim_shopify_button"):
            app.toggle_sim_shopify_button(self.sim_shopify_switch.get())

    def run_csv_patch(self):
        from tkinter import filedialog, messagebox
        import threading

        file_path = filedialog.askopenfilename(
            title="Select CSV to Patch Conditions",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        def _patch_worker():
            try:
                self.patch_btn.configure(state="disabled", text="Patching...")
                from import_engine import patch_conditions_from_csv
                updated, missing = patch_conditions_from_csv(file_path)
                messagebox.showinfo("Patch Complete", f"Successfully patched {updated} items.\nCould not find {missing} items from the CSV.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to patch: {e}")
            finally:
                def reset_btn():
                    try:
                        self.patch_btn.configure(state="normal", text="🩹 Patch CSV")
                    except Exception:
                        pass
                self.after(0, reset_btn)

        threading.Thread(target=_patch_worker, daemon=True).start()

    def run_csv_import(self):
        from tkinter import filedialog, messagebox
        import threading
        import os
        from import_engine import process_csv_import

        csv_path = filedialog.askopenfilename(
            title="Select Export CSV to Import",
            filetypes=[("CSV files", "*.csv")],
            initialdir=os.path.expanduser("~")
        )
        if not csv_path:
            return

        # Create Progress Modal
        progress_modal = ctk.CTkToplevel(self)
        progress_modal.title("Importing CSV...")
        progress_modal.geometry("400x150")
        progress_modal.transient(self.winfo_toplevel())
        progress_modal.grab_set()

        lbl = ctk.CTkLabel(progress_modal, text="Parsing and Importing CSV. Please wait...", font=ctk.CTkFont(weight="bold"))
        lbl.pack(pady=(20, 10))

        progress_bar = ctk.CTkProgressBar(progress_modal, width=300)
        progress_bar.pack(pady=10)
        progress_bar.set(0)

        pct_lbl = ctk.CTkLabel(progress_modal, text="0%")
        pct_lbl.pack()

        def update_progress(current, total):
            def _update():
                progress = current / total if total > 0 else 0
                progress_bar.set(progress)
                pct_lbl.configure(text=f"{int(progress * 100)}% ({current}/{total})")
            self.after(0, _update)

        def import_worker():
            def do_refresh():
                try:
                    self.after(0, lambda: self.winfo_toplevel().frames["studio"].refresh_staging_dock())
                except Exception:
                    pass

            success = process_csv_import(csv_path, refresh_callback=do_refresh, progress_callback=update_progress)
            self.after(0, lambda: self._on_import_complete(success, progress_modal))

        threading.Thread(target=import_worker, daemon=True).start()

    def _on_import_complete(self, success, modal):
        from tkinter import messagebox
        modal.destroy()
        if success:
            messagebox.showinfo("Import Complete", "CSV Import completed successfully! Cards have been added to the Review queue.")
            self.refresh_callback()
        else:
            messagebox.showerror("Import Failed", "CSV Import encountered errors. Please check the console for details.")

    def run_fetch_images(self):
        from tkinter import messagebox
        import threading
        import os
        import requests
        from rapidfuzz import fuzz
        from database import db_session, InventoryItem, StagingItem
        from api_client import PokemonAPI

        # Create Progress Modal
        progress_modal = ctk.CTkToplevel(self)
        progress_modal.title("Fetching Images...")
        progress_modal.geometry("400x150")
        progress_modal.transient(self.winfo_toplevel())
        progress_modal.grab_set()
        
        lbl = ctk.CTkLabel(progress_modal, text="Validating and fetching images. Please wait...", font=ctk.CTkFont(weight="bold"))
        lbl.pack(pady=(20, 10))
        
        progress_bar = ctk.CTkProgressBar(progress_modal, width=300)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        pct_lbl = ctk.CTkLabel(progress_modal, text="0%")
        pct_lbl.pack()

        def update_progress(current, total):
            def _update():
                progress = current / total if total > 0 else 0
                progress_bar.set(progress)
                pct_lbl.configure(text=f"{int(progress * 100)}% ({current}/{total})")
            # Schedule safely on main thread
            self.after(0, _update)

        def fetch_worker():
            api = PokemonAPI()
            
            inv_items = db_session.query(InventoryItem).filter(
                (InventoryItem.image_locked == False) & 
                (InventoryItem.card_type != 'Sealed')
            ).all()
            
            staging_items = db_session.query(StagingItem).filter(
                (StagingItem.image_locked == False) & 
                (StagingItem.card_type != 'Sealed')
            ).all()
            
            total = len(inv_items) + len(staging_items)
            if total == 0:
                self.after(0, progress_modal.destroy)
                self.after(0, lambda: messagebox.showinfo("Done", "No cards found to validate!"))
                return
                
            fetched_count = 0
            rejected_count = 0
            idx = 1
            
            def process_item(item, is_staging=False):
                nonlocal fetched_count, rejected_count
                res = api.fetch_card_data(set_name=item.set_name, sequence_number=item.sequence_number, ocr_name=item.name)
                
                def reject_image():
                    nonlocal rejected_count
                    rejected_count += 1
                    if is_staging:
                        item.image_path = ""
                    else:
                        item.image_url = ""
                    # Delete local thumbnail
                    thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
                    if os.path.exists(thumb_path):
                        try:
                            os.remove(thumb_path)
                        except Exception:
                            pass

                if res and res.get('high_res_image') and res.get('clean_name'):
                    # Verify Match
                    score = fuzz.WRatio(item.name.lower(), res['clean_name'].lower())
                    if score >= 65:
                        if is_staging:
                            item.image_path = res['high_res_image']
                        else:
                            item.image_url = res['high_res_image']
                            
                        # Download or copy thumbnail
                        try:
                            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
                            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                            
                            high_res = res['high_res_image']
                            if high_res.startswith('http'):
                                img_resp = requests.get(high_res, timeout=5)
                                if img_resp.status_code == 200:
                                    with open(thumb_path, 'wb') as f:
                                        f.write(img_resp.content)
                            elif os.path.exists(high_res):
                                import shutil
                                shutil.copyfile(high_res, thumb_path)
                        except Exception as e:
                            print(f"[!] Failed to download/copy thumbnail for {item.sku}: {e}")

                        fetched_count += 1
                    else:
                        print(f"[!] REJECTED: '{item.name}' matched with '{res['clean_name']}' (Score: {score:.0f}%)")
                        reject_image()
                else:
                    reject_image()
            
            for item in inv_items:
                print(f"[*] Validating Image: {item.name} [{idx}/{total}]")
                process_item(item, is_staging=False)
                update_progress(idx, total)
                idx += 1
                
            for item in staging_items:
                print(f"[*] Validating Image (Staging): {item.name} [{idx}/{total}]")
                process_item(item, is_staging=True)
                update_progress(idx, total)
                idx += 1
            
            db_session.commit()
            self.after(0, progress_modal.destroy)
            self.after(0, lambda: messagebox.showinfo("Done", f"Validation Complete.\n\nVerified/Fetched: {fetched_count}\nRejected/Deleted: {rejected_count}"))
            self.after(0, self.refresh_callback)
            try:
                self.after(0, lambda: self.winfo_toplevel().frames["studio"].refresh_staging_dock())
            except Exception:
                pass

        threading.Thread(target=fetch_worker, daemon=True).start()


    def add_shipping_rule(self):
        from database import db_session, ShippingRule
        from tkinter import messagebox
        try:
            min_p = float(self.min_entry.get())
            max_p = float(self.max_entry.get())
            add_p = float(self.add_entry.get())
            c_type = self.type_menu.get()
            
            new_rule = ShippingRule(min_price=min_p, max_price=max_p, additional_cost=add_p, card_type=c_type)
            db_session.add(new_rule)
            db_session.commit()
            
            self.min_entry.delete(0, 'end')
            self.max_entry.delete(0, 'end')
            self.add_entry.delete(0, 'end')
            self.refresh_shipping_rules()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.")

    def refresh_shipping_rules(self):
        for w in self.rules_scroll.winfo_children():
            w.destroy()
            
        from database import db_session, ShippingRule
        rules = db_session.query(ShippingRule).all()
        for r in rules:
            f = ctk.CTkFrame(self.rules_scroll, fg_color="#18181B", corner_radius=4)
            f.pack(fill="x", pady=2, padx=2)
            lbl = f"{r.card_type}: ${r.min_price:.2f} to ${r.max_price:.2f} -> Add ${r.additional_cost:.2f}"
            ctk.CTkLabel(f, text=lbl).pack(side="left", padx=10)
            
            def del_rule(rule_id=r.id):
                item = db_session.query(ShippingRule).get(rule_id)
                db_session.delete(item)
                db_session.commit()
                self.refresh_shipping_rules()
                
            ctk.CTkButton(f, text="❌", width=30, fg_color="#EF4444", command=del_rule).pack(side="right", padx=5)

    def open_set_names_editor(self):
        SetNamesDialog(self)

    def create_setting_row(self, master, row, title, subtitle, widget):
        text_container = ctk.CTkFrame(master, fg_color="transparent")
        text_container.grid(row=row, column=0, sticky="w", padx=20, pady=15)
        ctk.CTkLabel(text_container, text=title, font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text_container, text=subtitle, font=ctk.CTkFont(size=11), text_color="#8E8E8E").pack(anchor="w")
        widget.grid(row=row, column=1, sticky="e", padx=20, pady=15)
        return widget

    def export_db_backup(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database Files", "*.db")],
            initialfile="card_shop_backup.db",
            title="Export Database Backup"
        )
        if dest:
            try:
                shutil.copy2(DB_PATH, dest)
                messagebox.showinfo("Success", f"Database successfully backed up to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export database: {e}")

    def import_db_backup(self):
        src = filedialog.askopenfilename(
            filetypes=[("Database Files", "*.db")],
            title="Select Database Backup to Import"
        )
        if src:
            if messagebox.askyesno("WARNING: Full Database Overwrite", "This will completely wipe your current database and replace it with the selected backup.\n\nThe application will close after importing.\n\nAre you sure you want to proceed?"):
                try:
                    shutil.copy2(src, DB_PATH)
                    messagebox.showinfo("Import Successful", "The database has been successfully restored.\nThe application will now close. Please restart it to load the new data.")
                    os._exit(0)
                except Exception as e:
                    messagebox.showerror("Import Error", f"Failed to import database: {e}")

    def parse_float(self, val_str, default=0.0):
        try:
            return float(str(val_str).replace('$', '').replace('%', '').strip())
        except ValueError:
            return default

    def export_inventory_to_excel(self):
        import threading
        def _export():
            try:
                from openpyxl import Workbook
                from openpyxl.drawing.image import Image as OpenpyxlImage
                import qrcode
                import os
                import tempfile
                from database import db_session, InventoryItem
                from tkinter import messagebox
                
                self.after(0, lambda: self.export_btn.configure(state="disabled", text="⏳ Exporting..."))
                
                sort_option = self.export_sort_menu.get()
                query = db_session.query(InventoryItem).filter(InventoryItem.stock > 0)
                
                if sort_option == "Price: High to Low":
                    query = query.order_by(InventoryItem.price.desc())
                elif sort_option == "Price: Low to High":
                    query = query.order_by(InventoryItem.price.asc())
                elif sort_option == "Newest First":
                    query = query.order_by(InventoryItem.date_added.desc())
                else:
                    query = query.order_by(InventoryItem.name.asc())
                    
                items = query.all()
                wb = Workbook()
                ws = wb.active
                ws.title = "Inventory"
                
                ws.append(["Name", "Set Name", "Set Number", "SKU", "QR Code"])
                ws.column_dimensions['A'].width = 40
                ws.column_dimensions['B'].width = 30
                ws.column_dimensions['C'].width = 15
                ws.column_dimensions['D'].width = 25
                ws.column_dimensions['E'].width = 15
                
                temp_dir = tempfile.mkdtemp()
                
                for i, item in enumerate(items, start=2):
                    ws.row_dimensions[i].height = 75
                    ws.cell(row=i, column=1, value=item.name)
                    ws.cell(row=i, column=2, value=item.set_name)
                    ws.cell(row=i, column=3, value=item.sequence_number)
                    ws.cell(row=i, column=4, value=item.sku)
                    
                    qr = qrcode.make(item.sku)
                    qr = qr.resize((100, 100))
                    temp_path = os.path.join(temp_dir, f"{item.sku}.png")
                    qr.save(temp_path)
                    
                    img = OpenpyxlImage(temp_path)
                    ws.add_image(img, f"E{i}")
                
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                export_path = os.path.join(downloads_path, "Inventory_Export.xlsx")
                
                counter = 1
                while os.path.exists(export_path):
                    export_path = os.path.join(downloads_path, f"Inventory_Export_{counter}.xlsx")
                    counter += 1
                    
                wb.save(export_path)
                
                self.after(0, lambda path=export_path: messagebox.showinfo("Export Successful", f"Inventory exported to:\n{path}"))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("Export Failed", f"An error occurred: {e}"))
            finally:
                self.after(0, lambda: self.export_btn.configure(state="normal", text="Export Inventory to Excel"))
                
        threading.Thread(target=_export, daemon=True).start()

    def open_export_selected_modal(self):
        ExportSelectedModal(self)

    def save_settings(self):
        try:
            settings = db_session.query(SystemSettings).first()
            if not settings: settings = SystemSettings(id=1); db_session.add(settings)
            
            settings.buy_percentage = self.parse_float(self.buy_entry.get(), settings.buy_percentage if settings else 0.70)
            settings.trade_percentage = self.parse_float(self.trade_entry.get(), settings.trade_percentage if settings else 0.80)
            settings.rounding_strategy = self.rounding_menu.get()
            settings.resticker_threshold = self.parse_float(self.resticker_entry.get(), settings.resticker_threshold if settings else 2.00)
            
            settings.markup_type = self.markup_type_menu.get()
            settings.markup_value = self.parse_float(self.markup_val_entry.get(), settings.markup_value if settings else 0.0)
            settings.rounding_rule = self.shop_rounding_menu.get()
            
            settings.omit_graded_from_recon = bool(self.omit_graded_switch.get())
            settings.gmail_monitor_enabled = bool(self.gmail_monitor_switch.get())
            settings.gmail_address = self.gmail_addr_entry.get()
            settings.gmail_app_password = self.gmail_pass_entry.get()
            settings.gmail_folder = self.gmail_folder_entry.get()
            
            db_session.commit()
            
            # Restart or stop the monitor if toggled
            from services.gmail_monitor import get_gmail_monitor
            monitor = get_gmail_monitor()
            if settings.gmail_monitor_enabled:
                monitor.start()
            else:
                monitor.stop()
                
            messagebox.showinfo("Success", "Settings saved.")
            self.refresh_callback()
        except ValueError:
            messagebox.showerror("Error", "Check numeric values.")

    def toggle_gmail_monitor(self):
        pass # The actual state change logic is handled on Save Settings

    def test_gmail_connection(self):
        user = self.gmail_addr_entry.get().strip()
        pwd = self.gmail_pass_entry.get().strip()
        folder = self.gmail_folder_entry.get().strip()
        
        if not user or not pwd:
            messagebox.showerror("Test Failed", "Please enter a Gmail Address and App Password.")
            return
            
        self.test_gmail_btn.configure(state="disabled", text="Testing...")
        import threading
        
        def _test():
            try:
                import imaplib
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(user, pwd)
                status, _ = mail.select(f'"{folder}"')
                if status != "OK":
                    self.after(0, lambda: messagebox.showerror("Connection Failed", f"Logged in successfully, but could not find the folder/label '{folder}'."))
                else:
                    self.after(0, lambda: messagebox.showinfo("Connection Success", f"Successfully connected to Gmail and verified folder '{folder}'!"))
                mail.logout()
            except imaplib.IMAP4.error as e:
                self.after(0, lambda e=e: messagebox.showerror("Connection Failed", f"Invalid Credentials. Make sure you are using an App Password, not your standard Google password.\n\nDetails: {e}"))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("Connection Failed", f"Network or IMAP error:\n{e}"))
            finally:
                self.after(0, lambda: self.test_gmail_btn.configure(state="normal", text="Test Connection"))
                
        threading.Thread(target=_test, daemon=True).start()

    def on_wipe_inventory_clicked(self):
        if messagebox.askyesno("Confirm Wipe", "Are you absolutely sure you want to delete all inventory data? This cannot be undone."):
            DatabaseResetDialog(self, self.execute_wipe)
            
    def execute_wipe(self, include_purchases):
        from database import wipe_all_inventory
        try:
            wipe_all_inventory(include_purchases)
            messagebox.showinfo("Success", "Database wiped successfully.")
            self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to wipe database: {e}")

class MainDashboard(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure((0, 1), weight=1)
        
        # Stats Grid
        self.val_label = self.create_stat_card("PORTFOLIO VALUE", "$0.00", 0, 0)
        self.count_label = self.create_stat_card("ACTIVE STOCK COUNT", "0", 0, 1)
        self.margin_label = self.create_stat_card("OPERATIONAL MARGIN", "0%", 1, 0)
        self.stagnant_label = self.create_stat_card("PAPERWEIGHT ALERT", "0 ITEMS", 1, 1, color="#E74C3C")
        self.trade_credit_label = self.create_stat_card("TRADE CREDIT (30D)", "$0.00", 2, 0, color="#3b8ed0")
        self.profit_30d_label = self.create_stat_card("CASH PROFIT (30D)", "$0.00", 2, 1, color="#2fa572")
        
        self.refresh()

    def create_stat_card(self, title, initial, row, col, color="#007ACC"):
        card = ctk.CTkFrame(self, corner_radius=12, fg_color="#1A1A1A", border_color="#2D2D2D", border_width=1)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(card, text=title, font=APP_FONT_SM, text_color="#A0A0A0").pack(pady=(20, 0))
        lbl = ctk.CTkLabel(card, text=initial, font=APP_FONT_TITLE, text_color=color)
        lbl.pack(pady=5)
        return lbl

    def refresh(self):
        # 1. Basic Metrics
        total_val = db_session.query(func.sum(InventoryItem.price * InventoryItem.stock)).scalar() or 0
        total_count = db_session.query(func.sum(InventoryItem.stock)).scalar() or 0
        
        # 2. Operational Margin
        sales_stats = db_session.query(func.sum(Sale.sold_price), func.sum(Sale.profit)).filter(Sale.sold_price > 0).first()
        revenue = sales_stats[0] or 0
        profit = sales_stats[1] or 0
        margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # 3. Paperweight (Stagnant) items
        settings = db_session.query(SystemSettings).first()
        days = settings.paperweight_days if settings else 60
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        stagnant_count = db_session.query(func.sum(InventoryItem.stock)).filter(InventoryItem.date_added < cutoff).scalar() or 0

        self.val_label.configure(text=f"${total_val:,.2f}")
        self.count_label.configure(text=f"{int(total_count)} UNITS")
        self.margin_label.configure(text=f"{margin:.1f}%")
        self.stagnant_label.configure(text=f"{int(stagnant_count)} ITEMS")

class TradeHistoryFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header & Filter
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(header_f, text="TRANSACTION LOG & TRADE HISTORY", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=10)
        
        self.export_btn = ctk.CTkButton(header_f, text="📤 Export CSV", command=self.export_sales_csv, fg_color="#3b8ed0", hover_color="#2c6a9b", width=120)
        self.export_btn.pack(side="right", padx=10)
        
        self.clear_btn = ctk.CTkButton(header_f, text="🗑️ Clear History", command=self.clear_trade_history, fg_color="#944747", hover_color="#7A3B3B", width=120)
        self.clear_btn.pack(side="right", padx=10)
        
        self.filter_entry = ctk.CTkEntry(header_f, placeholder_text="Filter by Name, SKU, or Type...", width=300, border_color="#333333")
        self.filter_entry.pack(side="right", padx=10)
        self.filter_entry.bind("<KeyRelease>", lambda e: self.refresh_list())

        # List Area
        self.scroll = ctk.CTkScrollableFrame(self, label_text="HISTORICAL RECORDS")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure((0,1,2,3,4,5), weight=1)

        self.refresh_list()

    def clear_trade_history(self):
        from tkinter import messagebox
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to permanently clear all historical transaction records?"):
            try:
                from database import db_session, Sale
                db_session.query(Sale).delete(synchronize_session=False)
                db_session.commit()
                messagebox.showinfo("Success", "Transaction log history cleared successfully.")
                self.refresh_list()
                if self.refresh_callback:
                    self.refresh_callback()
            except Exception as e:
                db_session.rollback()
                messagebox.showerror("Error", f"Failed to clear history: {e}")

    def refresh_list(self):
        for child in self.scroll.winfo_children(): child.destroy()
        
        headers = ["Timestamp", "Type", "Item Detail", "SKU", "Amount", "Profit"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.scroll, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=i, padx=5, pady=5, sticky="w")

        query = self.filter_entry.get().lower()
        # Fetch last 200 sales/trades
        sales = db_session.query(Sale).filter(
            (Sale.item_name.ilike(f"%{query}%")) | 
            (Sale.sku.ilike(f"%{query}%")) | 
            (Sale.transaction_type.ilike(f"%{query}%"))
        ).order_by(Sale.timestamp.desc()).limit(200).all()

        for idx, s in enumerate(sales, 1):
            ts = s.timestamp.strftime("%Y-%m-%d %H:%M")
            ctk.CTkLabel(self.scroll, text=ts, font=("Arial", 11)).grid(row=idx, column=0, padx=5, pady=2, sticky="w")
            
            # Type Color Coding
            type_color = "#2fa572" if s.transaction_type == "Cash" else "#3b8ed0" if "Trade" in s.transaction_type else "#d35400"
            ctk.CTkLabel(self.scroll, text=s.transaction_type, text_color=type_color, font=ctk.CTkFont(weight="bold")).grid(row=idx, column=1, padx=5, pady=2, sticky="w")
            
            ctk.CTkLabel(self.scroll, text=s.item_name, anchor="w").grid(row=idx, column=2, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(self.scroll, text=s.sku, font=("Courier", 11)).grid(row=idx, column=3, padx=5, pady=2, sticky="w")
            
            # Show amount paid/received
            amt = s.sold_price if s.sold_price > 0 else s.trade_in_value
            ctk.CTkLabel(self.scroll, text=f"${amt:.2f}").grid(row=idx, column=4, padx=5, pady=2, sticky="w")
            
            # Profit
            prof_color = "#2fa572" if s.profit >= 0 else "#944747"
            ctk.CTkLabel(self.scroll, text=f"${s.profit:.2f}", text_color=prof_color).grid(row=idx, column=5, padx=5, pady=2, sticky="w")

    def export_sales_csv(self):
        from tkinter import filedialog, messagebox
        import csv
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Sales Log"
        )
        
        if not file_path:
            return
            
        try:
            query_str = self.filter_entry.get().lower()
            if query_str:
                sales = db_session.query(Sale).filter(
                    (Sale.item_name.ilike(f"%{query_str}%")) | 
                    (Sale.sku.ilike(f"%{query_str}%")) | 
                    (Sale.transaction_type.ilike(f"%{query_str}%"))
                ).order_by(Sale.timestamp.desc()).all()
            else:
                sales = db_session.query(Sale).order_by(Sale.timestamp.desc()).all()
                
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Type", "Item Name", "SKU", "Sold Price", "Profit", "Trade-in Value", "Processing Fees", "Trade Credit Deduction", "Net Revenue"])
                
                for s in sales:
                    writer.writerow([
                        s.timestamp.strftime("%Y-%m-%d %H:%M:%S") if s.timestamp else "",
                        s.transaction_type or "",
                        s.item_name or "",
                        s.sku or "",
                        f"{s.sold_price:.2f}" if s.sold_price is not None else "0.00",
                        f"{s.profit:.2f}" if s.profit is not None else "0.00",
                        f"{s.trade_in_value:.2f}" if s.trade_in_value is not None else "0.00",
                        f"{s.processing_fees:.2f}" if s.processing_fees is not None else "0.00",
                        f"{s.trade_credit_deduction:.2f}" if s.trade_credit_deduction is not None else "0.00",
                        f"{s.net_revenue:.2f}" if s.net_revenue is not None else "0.00"
                    ])
            messagebox.showinfo("Export Complete", f"Successfully exported {len(sales)} sales records to CSV.")
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while exporting: {e}")

ctk.set_appearance_mode("Dark")



class StagingDockFrame(ctk.CTkFrame):
    def __init__(self, master, update_callback):
        super().__init__(master, fg_color="#121214", border_width=1, border_color="#1F1F23", corner_radius=12)
        self.update_callback = update_callback
        self.label_format_var = tk.StringVar(value="QR")
        self.current_page = 1
        self.page_size = 15
        
        self.setup_ui()

    def setup_ui(self):
        dock_header = ctk.CTkFrame(self, fg_color="transparent")
        dock_header.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(dock_header, text="STAGING DOCK", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=5)

        self.clear_btn = ctk.CTkButton(dock_header, text="🗑️ Clear", fg_color="#EF4444", hover_color="#DC2626", font=("Segoe UI", 11, "bold"), height=26, width=60, command=self.clear_staging)
        self.clear_btn.pack(side="right", padx=5)

        self.apply_trades_btn = ctk.CTkButton(
            dock_header, text="💰 Apply Trade Values",
            fg_color="#D97706", hover_color="#B45309",
            font=("Segoe UI", 11, "bold"), height=26, width=150,
            command=self.apply_pending_trades
        )
        self.apply_trades_btn.pack(side="right", padx=5)

        self.format_menu = ctk.CTkOptionMenu(dock_header, values=["QR", "Barcode"], variable=self.label_format_var, width=90, height=26, font=("Segoe UI", 11, "bold"), button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00")
        self.format_menu.pack(side="right", padx=5)

        # Filter Frame (Search, Sort, Tabs)
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.filter_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(self.filter_frame, placeholder_text="Filter by Name, Set, or Seq...", height=30, border_color="#333333")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", lambda e: self.reset_page_and_refresh())
        
        self.sort_var = ctk.StringVar(value="Import Order (CSV)")
        self.sort_dropdown = ctk.CTkOptionMenu(
            self.filter_frame, 
            variable=self.sort_var, 
            values=["Import Order (CSV)", "Newest First", "Market Price (High-Low)", "Market Price (Low-High)", "Name (A-Z)", "Set (A-Z)"],
            command=lambda v: self.reset_page_and_refresh(),
            height=30,
            button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00"
        )
        self.sort_dropdown.grid(row=0, column=1, sticky="e", padx=(0, 5))
        
        self.filter_var = ctk.StringVar(value="All")
        self.seg_btn = ctk.CTkSegmentedButton(self.filter_frame, values=["All", "Singles", "Graded", "Sealed"], variable=self.filter_var, command=lambda v: self.reset_page_and_refresh(), height=30)
        self.seg_btn.grid(row=0, column=2, sticky="e")

        self.scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="PARSED CARDS STAGING QUEUE", label_font=("Segoe UI", 11, "bold"), label_text_color="#A1A1AA")
        self.scroll_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Pagination Controls
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.pagination_frame.grid_columnconfigure(1, weight=1)
        
        self.prev_btn = ctk.CTkButton(self.pagination_frame, text="⬅️ Previous", width=100, command=self.prev_page)
        self.prev_btn.grid(row=0, column=0, sticky="w")
        
        self.page_lbl = ctk.CTkLabel(self.pagination_frame, text="Page 1 of 1", font=ctk.CTkFont(weight="bold"))
        self.page_lbl.grid(row=0, column=1, padx=10)
        
        self.next_btn = ctk.CTkButton(self.pagination_frame, text="Next ➡️", width=100, command=self.next_page)
        self.next_btn.grid(row=0, column=2, sticky="e")

    def reset_page_and_refresh(self):
        self.current_page = 1
        self.refresh_staging_dock()
        self.after(10, lambda: self.scroll_container._parent_canvas.yview_moveto(0))

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_staging_dock()
            self.after(10, lambda: self.scroll_container._parent_canvas.yview_moveto(0))

    def next_page(self):
        self.current_page += 1
        self.refresh_staging_dock()
        self.after(10, lambda: self.scroll_container._parent_canvas.yview_moveto(0))

    def refresh_staging_dock(self):
        for child in self.scroll_container.winfo_children():
            child.destroy()

        try:
            db_session.commit() # Force sync to see background thread commits
        except Exception:
            pass
        
        query = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""
        active_tab = self.filter_var.get() if hasattr(self, 'filter_var') else "All"
        sort_choice = self.sort_var.get() if hasattr(self, 'sort_var') else "Import Order (CSV)"

        base_query = db_session.query(StagingItem)
        
        if query:
            base_query = base_query.filter(
                (StagingItem.name.ilike(f"%{query}%")) | 
                (StagingItem.set_name.ilike(f"%{query}%")) | 
                (StagingItem.sequence_number.ilike(f"%{query}%"))
            )
            
        if active_tab == "Singles":
            base_query = base_query.filter((StagingItem.card_type != 'Sealed') & (StagingItem.card_type != 'Graded') | (StagingItem.card_type == None))
        elif active_tab == "Sealed":
            base_query = base_query.filter(StagingItem.card_type == 'Sealed')
        elif active_tab == "Graded":
            base_query = base_query.filter(StagingItem.card_type == 'Graded')
            
        if sort_choice == "Market Price (High-Low)":
            base_query = base_query.order_by(StagingItem.market_price.desc())
        elif sort_choice == "Market Price (Low-High)":
            base_query = base_query.order_by(StagingItem.market_price.asc())
        elif sort_choice == "Name (A-Z)":
            base_query = base_query.order_by(StagingItem.name.asc())
        elif sort_choice == "Set (A-Z)":
            base_query = base_query.order_by(StagingItem.set_name.asc())
        elif sort_choice == "Newest First":
            base_query = base_query.order_by(StagingItem.timestamp.desc())
        else:
            base_query = base_query.order_by(StagingItem.id.asc())

        total_items = base_query.count()
        import math
        total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1

        if self.current_page > total_pages:
            self.current_page = total_pages

        if hasattr(self, 'page_lbl'):
            self.page_lbl.configure(text=f"Page {self.current_page} of {total_pages}")
            self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
            self.next_btn.configure(state="normal" if self.current_page < total_pages else "disabled")

        items = base_query.offset((self.current_page - 1) * self.page_size).limit(self.page_size).all()
        for item in items:
            self.create_compact_card_widget(item)

    def create_clickable_field(self, parent, label_prefix, field_name, value, item_id, font_config, text_color="#FFFFFF", glow_type="NONE"):
        if glow_type == "RED":
            border_color = "#FF3333"
            bg_color = "#2D1E1E"
            border_w = 2
        elif glow_type == "YELLOW":
            border_color = "#FFD700"
            bg_color = "#2D261E"
            border_w = 2
        else:
            border_color = "#18181B"
            bg_color = "transparent"
            border_w = 0

        # Clickable field wrapper frame
        glow_frame = ctk.CTkFrame(parent, fg_color=bg_color, border_width=border_w, border_color=border_color, corner_radius=6)
        glow_frame.current_value = value
        glow_frame.active_entry = None
        
        display_text = f"{label_prefix}{value}"
        lbl = ctk.CTkLabel(glow_frame, text=display_text, font=font_config, text_color=text_color, cursor="hand2", anchor="w")
        lbl.pack(padx=8, pady=4, fill="both", expand=True)

        def on_click(event):
            if glow_frame.active_entry is not None:
                return  # Already editable
            lbl.pack_forget()
            
            entry = ctk.CTkEntry(glow_frame, font=font_config, fg_color="#09090B", border_color="#6366F1", height=24)
            entry.insert(0, str(glow_frame.current_value))
            entry.pack(padx=2, pady=2, fill="x", expand=True)
            entry.focus()
            entry.select_range(0, tk.END)
            glow_frame.active_entry = entry

            def commit(event=None):
                new_val = entry.get()
                glow_frame.active_entry = None
                glow_frame.current_value = new_val
                if new_val == str(value):
                    self.refresh_staging_dock()
                else:
                    self.update_staging_field(item_id, field_name, new_val)
                    
            entry.bind("<Return>", commit)
            entry.bind("<FocusOut>", commit)

        lbl.bind("<Button-1>", on_click)
        glow_frame.make_editable = lambda: on_click(None)
        return glow_frame

    def create_compact_card_widget(self, item):
        card_frame = ctk.CTkFrame(self.scroll_container, fg_color="#18181B", border_width=1, border_color="#27272A", corner_radius=8)
        card_frame.pack(fill="x", padx=20, pady=10)
        
        card_frame.grid_columnconfigure(0, weight=0) # thumbnail
        card_frame.grid_columnconfigure(1, weight=1) # details
        card_frame.grid_columnconfigure(2, weight=0) # label preview

        # 1. Thumbnail Column
        if item.image_path and os.path.exists(item.image_path):
            try:
                import PIL.ImageOps
                img = Image.open(item.image_path)
                # Pad preserves aspect ratio and letterboxes (contain would be stretched by CTkImage size constraint)
                img = PIL.ImageOps.pad(img, (70, 70), method=Image.Resampling.LANCZOS, color="#18181B")
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=(70, 70))
                lbl = ctk.CTkLabel(card_frame, image=photo, text="")
                lbl.image = photo
                lbl.grid(row=0, column=0, padx=10, pady=10, sticky="n")
            except Exception:
                lbl = ctk.CTkLabel(card_frame, text="IMG ERR", font=("Segoe UI", 10), width=70, height=70, fg_color="#27272A")
                lbl.grid(row=0, column=0, padx=10, pady=10, sticky="n")
        else:
            lbl = ctk.CTkLabel(card_frame, text="NO IMG", font=("Segoe UI", 10), width=70, height=70, fg_color="#27272A")
            lbl.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        # 2. Details Column (Grid)
        details_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        details_frame.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="ew")
        details_frame.grid_columnconfigure(0, weight=1)
        details_frame.grid_columnconfigure(1, weight=1)
        details_frame.grid_columnconfigure(2, weight=1)
        details_frame.grid_columnconfigure(3, weight=1)

        # 3. Label Preview Column
        preview_lbl = ctk.CTkLabel(card_frame, text="NO LBL", font=("Segoe UI", 10, "bold"), width=80, height=80, fg_color="#27272A", text_color="#A1A1AA")
        preview_lbl.grid(row=0, column=2, padx=10, pady=10, sticky="n")

        # Parse ocr_metadata for glows
        meta = json.loads(item.ocr_metadata or '{}')
        scores = meta.get('scores', {})
        flags = meta.get('flags', {})

        # Evaluate Glows
        name_glow = "YELLOW" if scores.get('name', 100) < 85 else "NONE"
        set_glow = "YELLOW" if scores.get('set_name', 100) < 85 else "NONE"
        num_glow = "YELLOW" if scores.get('sequence_number', 100) < 85 else "NONE"
        
        mkt_flag = flags.get('market_price', 'NONE')
        if mkt_flag == "TOMATO":
            mkt_glow = "RED"
        elif mkt_flag == "GOLD" or scores.get('market_price', 100) < 85:
            mkt_glow = "YELLOW"
        else:
            mkt_glow = "NONE"

        # Fonts configuration
        name_font = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        small_font = ctk.CTkFont(family="Segoe UI", size=10)

        # Row 0: Prominent Name (spans all 3 columns)
        name_widget = self.create_clickable_field(
            details_frame, "", "name", item.name or "Unknown Card", item.id,
            name_font, text_color="#FFFFFF", glow_type=name_glow
        )
        name_widget.grid(row=0, column=0, columnspan=4, pady=(0, 6), sticky="ew")

        # Row 1: Set, Number, Mkt Price
        set_widget = self.create_clickable_field(
            details_frame, "Set: ", "set_name", item.set_name or "N/A", item.id,
            small_font, text_color="#E4E4E7", glow_type=set_glow
        )
        set_widget.grid(row=1, column=0, padx=2, pady=2, sticky="ew")

        num_widget = self.create_clickable_field(
            details_frame, "No: ", "sequence_number", item.sequence_number or "N/A", item.id,
            small_font, text_color="#E4E4E7", glow_type=num_glow
        )
        num_widget.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        mkt_widget = self.create_clickable_field(
            details_frame, "Mkt: $", "market_price", f"{item.market_price:.2f}", item.id,
            small_font, text_color="#10B981", glow_type=mkt_glow
        )
        mkt_widget.grid(row=1, column=2, padx=2, pady=2, sticky="ew")

        game_widget = self.create_clickable_field(
            details_frame, "Game: ", "game", getattr(item, 'game', 'Pokemon'), item.id,
            small_font, text_color="#3b8ed0" if getattr(item, 'game', 'Pokemon') == 'Pokemon' else "#E11D48", glow_type="NONE"
        )
        game_widget.grid(row=1, column=3, padx=2, pady=2, sticky="ew")

        # Row 2: Variant, Condition, Type
        var_widget = self.create_clickable_field(
            details_frame, "Var: ", "variant", item.variant or "Standard", item.id,
            small_font, text_color="#A1A1AA", glow_type="NONE"
        )
        var_widget.grid(row=2, column=0, padx=2, pady=2, sticky="ew")

        cond_widget = self.create_clickable_field(
            details_frame, "Cond: ", "condition", item.condition or "Near Mint", item.id,
            small_font, text_color="#A1A1AA", glow_type="NONE"
        )
        cond_widget.grid(row=2, column=1, padx=2, pady=2, sticky="ew")

        type_widget = self.create_clickable_field(
            details_frame, "Type: ", "card_type", item.card_type or "Unknown", item.id,
            small_font, text_color="#A1A1AA", glow_type="NONE"
        )
        type_widget.grid(row=2, column=2, padx=2, pady=2, sticky="ew")

        # Row 3: Qty, Sug Price, Cost Basis
        qty_widget = self.create_clickable_field(
            details_frame, "Qty: ", "quantity", str(item.quantity), item.id,
            small_font, text_color="#A1A1AA", glow_type="NONE"
        )
        qty_widget.grid(row=3, column=0, padx=2, pady=2, sticky="ew")

        sug_widget = self.create_clickable_field(
            details_frame, "Sug: $", "suggested_price", f"{item.suggested_price:.2f}", item.id,
            small_font, text_color="#A1A1AA", glow_type="NONE"
        )
        sug_widget.grid(row=3, column=1, padx=2, pady=2, sticky="ew")

        cost_widget = self.create_clickable_field(
            details_frame, "Cost: $", "cost_basis", f"{item.cost_basis:.2f}", item.id,
            small_font, text_color="#A1A1AA", glow_type="NONE"
        )
        cost_widget.grid(row=3, column=2, padx=2, pady=2, sticky="ew")

        # Row 4: Action Panel (SKU code, copy barcode, promote, delete)
        f_actions = ctk.CTkFrame(details_frame, fg_color="transparent")
        f_actions.grid(row=4, column=0, columnspan=4, pady=(6, 0), sticky="ew")

        ctk.CTkLabel(f_actions, text=f"SKU: {item.sku}", font=("Courier New", 10, "bold"), text_color="#6366F1").pack(side="left")

        def get_field_val(widget):
            if hasattr(widget, 'active_entry') and widget.active_entry is not None:
                try:
                    return widget.active_entry.get()
                except Exception:
                    pass
            if hasattr(widget, 'current_value'):
                return widget.current_value
            return ""

        def on_refetch_clicked():
            # Make the Card Name, Set Name, and Number fields editable
            name_widget.make_editable()
            set_widget.make_editable()
            num_widget.make_editable()
            
            # Show Override button, hide Re-Fetch button
            refetch_btn.pack_forget()
            override_btn.pack(side="right", padx=3)

        def trigger_override():
            updated_name = get_field_val(name_widget)
            updated_set = get_field_val(set_widget)
            updated_number = get_field_val(num_widget)
            
            print(f"[UI Override] Forcing API query with manual entries: name='{updated_name}', set='{updated_set}', number='{updated_number}'")
            success = manual_api_refetch(item.id, updated_name, updated_set, updated_number)
            if success:
                self.refresh_staging_dock()
            else:
                messagebox.showerror("Override Failed", "Could not fetch card data with the provided manual values.")

        def generate_and_preview_label(fmt, copy_to_clipboard=True):
            def _bg_gen():
                try:
                    from logic import generate_label, generate_item_barcode
                    import PIL.ImageOps
                    import pyperclip
                    img = generate_label(item.sku, format=fmt)
                    
                    # Save to disk to ensure it's ready for printing later
                    generate_item_barcode(item.sku, format=fmt)
                    
                    # Pad for preview display
                    img_padded = PIL.ImageOps.pad(img, (80, 80), method=Image.Resampling.LANCZOS, color="#27272A")
                    photo = ctk.CTkImage(light_image=img_padded, dark_image=img_padded, size=(80, 80))
                    
                    def _update_lbl():
                        if preview_lbl.winfo_exists():
                            preview_lbl.configure(image=photo, text="")
                            preview_lbl.image = photo
                            if copy_to_clipboard:
                                pyperclip.copy(item.sku)
                                
                    if preview_lbl.winfo_exists():
                        preview_lbl.after(0, _update_lbl)
                except Exception as e:
                    print(f"Failed to generate label preview: {e}")
            import threading
            threading.Thread(target=_bg_gen, daemon=True).start()

        # Do not generate QR/barcode automatically to keep extras to a minimum

        ctk.CTkButton(f_actions, text="❌ Delete", width=60, height=22, fg_color="#EF4444", hover_color="#DC2626", font=("Segoe UI", 10, "bold"), command=lambda i=item: self.delete_staged_item(i)).pack(side="right", padx=3)
        ctk.CTkButton(f_actions, text="✅ Promote", width=70, height=22, fg_color="#10B981", hover_color="#059669", font=("Segoe UI", 10, "bold"), command=lambda i=item: self.confirm_single_item(i)).pack(side="right", padx=3)

        def set_image_url(i=item):
            dialog = ctk.CTkInputDialog(text="Enter image URL for this card:", title="Set Image URL")
            url = dialog.get_input()
            if url is not None:
                val = url.strip()
                if val.startswith("http"):
                    import requests, os
                    try:
                        resp = requests.get(val, timeout=5)
                        resp.raise_for_status()
                        thumb_path = os.path.join('static', 'scraped_thumbnails', f"{i.sku}.png")
                        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                        with open(thumb_path, 'wb') as f:
                            f.write(resp.content)
                        # Save the URL to DB, not the local path, so it syncs!
                        i.image_path = val
                    except Exception as e:
                        print(f"Failed to download staging image: {e}")
                        i.image_path = val
                else:
                    i.image_path = val
                db_session.commit()
                self.refresh_staging_dock()

        ctk.CTkButton(f_actions, text="🔗 URL", width=60, height=22, fg_color="#3B82F6", hover_color="#2563EB", font=("Segoe UI", 10, "bold"), command=set_image_url).pack(side="right", padx=3)
        
        btn_box = ctk.CTkFrame(f_actions, fg_color="transparent")
        btn_box.pack(side="right", padx=3)
        ctk.CTkButton(btn_box, text="📋 Copy QR", width=80, height=20, fg_color="#4B5563", hover_color="#374151", font=("Segoe UI", 9), command=lambda: generate_and_preview_label("QR")).pack(pady=1)
        ctk.CTkButton(btn_box, text="📋 Copy Barcode", width=80, height=20, fg_color="#4B5563", hover_color="#374151", font=("Segoe UI", 9), command=lambda: generate_and_preview_label("Barcode")).pack(pady=1)

        override_btn = ctk.CTkButton(f_actions, text="⚡ Override", width=70, height=22, fg_color="#F59E0B", hover_color="#D97706", font=("Segoe UI", 10, "bold"), command=trigger_override)

        refetch_btn = ctk.CTkButton(f_actions, text="🔄 Re-Fetch", width=70, height=22, fg_color="#6366F1", hover_color="#4F46E5", font=("Segoe UI", 10), command=on_refetch_clicked)
        refetch_btn.pack(side="right", padx=3)

    def update_staging_field(self, item_id, field, value):
        try:
            import re
            item = db_session.query(StagingItem).filter_by(id=item_id).first()
            if not item:
                return

            if field in ['market_price', 'suggested_price', 'cost_basis']:
                value = float(re.sub(r'[^0-9.]', '', str(value))) if value else 0.0
            elif field == 'quantity':
                value = int(re.sub(r'\D', '', str(value))) if value else 1
            else:
                value = str(value)

            setattr(item, field, value)

            # Clear warning/consensuses in ocr_metadata
            meta = json.loads(item.ocr_metadata or '{}')
            scores = meta.setdefault('scores', {})
            flags = meta.setdefault('flags', {})

            # Reset OCR score to 100 (user verified)
            scores[field] = 100.0
            if field in flags:
                flags[field] = "NONE"

            # Check if name is fully clear
            if scores.get('name', 100) >= 85 and flags.get('market_price') != "TOMATO":
                item.needs_review = False

            item.ocr_metadata = json.dumps(meta)

            # Recalculate rules if market price changed
            if field == 'market_price':
                settings = db_session.query(SystemSettings).first()
                rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
                item.suggested_price = calculate_suggested_price(item.market_price, rule)
                item.cost_basis = round(item.market_price * (settings.buy_percentage if settings else 0.7), 2)

            db_session.commit()
            self.refresh_staging_dock()
            self.update_callback()
        except Exception as e:
            print(f"[!] Staging update error: {e}")

    def delete_staged_item(self, item):
        remove_signature_from_cache(
            item.name or "", 
            item.set_name or "", 
            item.sequence_number or "", 
            item.variant or "", 
            item.condition or ""
        )
        db_session.delete(item)
        db_session.commit()
        self.refresh_staging_dock()
        self.update_callback()

    def confirm_single_item(self, staging_item):
        import os, shutil
        display_text = f"Card: {staging_item.name}\nMarket Price: ${(staging_item.market_price or 0.0):.2f}"
        
        dialog = ctk.CTkInputDialog(text=f"{display_text}\n\nHow much did you pay for this card? ($)", title="Enter Cost Basis")
        result = dialog.get_input()
        if result is None:
            return # Cancelled
            
        try:
            val = result.strip()
            cost = float(val.replace('$', '').replace(',', '')) if val else 0.00
        except ValueError:
            cost = 0.00
            
        try:
            import re
            def normalize_string(s):
                return re.sub(r'[^a-z0-9]', '', str(s).lower()) if s else ""
                
            candidates = db_session.query(InventoryItem).filter(
                InventoryItem.set_name == staging_item.set_name,
                InventoryItem.sequence_number == staging_item.sequence_number,
                InventoryItem.variant == staging_item.variant,
                InventoryItem.condition == staging_item.condition
            ).all()
            
            existing_item = next((c for c in candidates if normalize_string(c.name) == normalize_string(staging_item.name)), None)

            from logic import calculate_shop_listing_price
            calc_shop_price = calculate_shop_listing_price(staging_item.market_price or 0.0, staging_item.card_type)

            if existing_item:
                total_qty = existing_item.stock + staging_item.quantity
                if total_qty > 0:
                    new_avg_cost = ((existing_item.cost * existing_item.stock) + (cost * staging_item.quantity)) / total_qty
                    existing_item.cost = round(new_avg_cost, 2)

                existing_item.stock = total_qty
                existing_item.price = staging_item.market_price
                existing_item.shop_listing_price = calc_shop_price
                existing_item.sticker_price = staging_item.suggested_price
                if staging_item.image_path:
                    existing_item.image_url = staging_item.image_path
                    existing_item.custom_image_url = staging_item.image_path
                    if os.path.exists(staging_item.image_path):
                        dest_path = os.path.join('static', 'scraped_thumbnails', f"{existing_item.sku}.png")
                        if staging_item.image_path != dest_path:
                            try:
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                shutil.copy(staging_item.image_path, dest_path)
                            except Exception:
                                pass
                
                from database import SyncOutbox
                outbox_stock = SyncOutbox(action_type='stock_update', sku=existing_item.sku, quantity_change=staging_item.quantity, new_price=existing_item.shop_listing_price)
                db_session.add(outbox_stock)

                new_purchase = PurchaseRecord(sku=existing_item.sku, quantity=staging_item.quantity, cost_per_unit=cost)
                db_session.add(new_purchase)
                
                remove_signature_from_cache(
                    staging_item.name or "", 
                    staging_item.set_name or "", 
                    staging_item.sequence_number or "", 
                    staging_item.variant or "", 
                    staging_item.condition or ""
                )
                db_session.delete(staging_item)
            else:
                promo_sku = staging_item.sku
                while db_session.query(InventoryItem).filter_by(sku=promo_sku).first() is not None:
                    promo_sku = f"CS-{os.urandom(2).hex().upper()}"

                if staging_item.image_path and os.path.exists(staging_item.image_path):
                    dest_path = os.path.join('static', 'scraped_thumbnails', f"{promo_sku}.png")
                    if staging_item.image_path != dest_path:
                        try:
                            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                            shutil.copy(staging_item.image_path, dest_path)
                            staging_item.image_path = dest_path
                        except Exception:
                            pass

                new_inv = InventoryItem(
                    sku=promo_sku,
                    name=staging_item.name,
                    set_name=staging_item.set_name,
                    sequence_number=staging_item.sequence_number,
                    cost=cost,
                    price=staging_item.market_price,
                    shop_listing_price=calc_shop_price,
                    sticker_price=staging_item.suggested_price,
                    card_type=staging_item.card_type,
                    variant=staging_item.variant,
                    condition=staging_item.condition,
                    stock=staging_item.quantity if staging_item.quantity else 1,
                    image_url=staging_item.image_path,
                    custom_image_url=staging_item.image_path
                )
                db_session.add(new_inv)
                new_purchase = PurchaseRecord(sku=new_inv.sku, quantity=new_inv.stock, cost_per_unit=cost)
                db_session.add(new_purchase)
                
                remove_signature_from_cache(
                    staging_item.name or "", 
                    staging_item.set_name or "", 
                    staging_item.sequence_number or "", 
                    staging_item.variant or "", 
                    staging_item.condition or ""
                )
                db_session.delete(staging_item)
                db_session.flush()
                generate_item_barcode(new_inv.sku, format=self.label_format_var.get())

            db_session.commit()
            clear_signatures_cache()
            self.refresh_staging_dock()
            self.update_callback()
        except Exception as e:
            db_session.rollback()
            messagebox.showerror("Promotion Error", f"Failed to promote item: {e}")

    def commit_batch(self):
        import os, shutil
        items = db_session.query(StagingItem).all()
        if not items:
            messagebox.showinfo("Empty Dock", "No items in staging queue to commit.")
            return

        total_market = sum([(it.market_price or 0.0) * (it.quantity or 1) for it in items])
        display_text = f"Lot of {len(items)} cards\nTotal Market Value: ${total_market:.2f}"
        
        dialog = ctk.CTkInputDialog(text=f"{display_text}\n\nHow much did you pay for this card/lot? ($)", title="Enter Cost Basis")
        result = dialog.get_input()
        if result is None:
            return # Cancelled
            
        try:
            val = result.strip()
            lot_cost = float(val.replace('$', '').replace(',', '')) if val else 0.00
        except ValueError:
            lot_cost = 0.00

        success_count = 0
        error_count = 0

        from logic import calculate_shop_listing_price

        for staging_item in items:
            try:
                # Apportion cost basis based on market value contribution
                if total_market > 0:
                    weight = ((staging_item.market_price or 0.0) * (staging_item.quantity or 1)) / total_market
                    total_item_cost = lot_cost * weight
                    cost = round(total_item_cost / (staging_item.quantity or 1), 2)
                else:
                    cost = round(lot_cost / sum(it.quantity or 1 for it in items), 2)
                    
                import re
                def normalize_string(s):
                    return re.sub(r'[^a-z0-9]', '', str(s).lower()) if s else ""
                    
                candidates = db_session.query(InventoryItem).filter(
                    InventoryItem.set_name == staging_item.set_name,
                    InventoryItem.sequence_number == staging_item.sequence_number,
                    InventoryItem.variant == staging_item.variant,
                    InventoryItem.condition == staging_item.condition
                ).all()
                
                existing_item = next((c for c in candidates if normalize_string(c.name) == normalize_string(staging_item.name)), None)

                calc_shop_price = calculate_shop_listing_price(staging_item.market_price or 0.0, staging_item.card_type)

                if existing_item:
                    total_qty = existing_item.stock + staging_item.quantity
                    if total_qty > 0:
                        new_avg_cost = ((existing_item.cost * existing_item.stock) + (cost * staging_item.quantity)) / total_qty
                        existing_item.cost = round(new_avg_cost, 2)

                    existing_item.stock = total_qty
                    existing_item.price = staging_item.market_price
                    existing_item.shop_listing_price = calc_shop_price
                    existing_item.sticker_price = staging_item.suggested_price
                    if staging_item.image_path:
                        existing_item.image_url = staging_item.image_path
                        existing_item.custom_image_url = staging_item.image_path
                        if os.path.exists(staging_item.image_path):
                            dest_path = os.path.join('static', 'scraped_thumbnails', f"{existing_item.sku}.png")
                            if staging_item.image_path != dest_path:
                                try:
                                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                    shutil.copy(staging_item.image_path, dest_path)
                                except Exception:
                                    pass

                    from database import SyncOutbox
                    outbox_stock = SyncOutbox(action_type='stock_update', sku=existing_item.sku, quantity_change=staging_item.quantity, new_price=existing_item.shop_listing_price)
                    db_session.add(outbox_stock)

                    new_purchase = PurchaseRecord(sku=existing_item.sku, quantity=staging_item.quantity, cost_per_unit=cost)
                    db_session.add(new_purchase)

                    remove_signature_from_cache(
                        staging_item.name or "", 
                        staging_item.set_name or "", 
                        staging_item.sequence_number or "",
                        staging_item.variant or "",
                        staging_item.condition or ""
                    )
                    db_session.delete(staging_item)
                else:
                    promo_sku = staging_item.sku
                    while db_session.query(InventoryItem).filter_by(sku=promo_sku).first() is not None:
                        promo_sku = f"CS-{os.urandom(2).hex().upper()}"

                    if staging_item.image_path and os.path.exists(staging_item.image_path):
                        dest_path = os.path.join('static', 'scraped_thumbnails', f"{promo_sku}.png")
                        if staging_item.image_path != dest_path:
                            try:
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                shutil.copy(staging_item.image_path, dest_path)
                                staging_item.image_path = dest_path
                            except Exception:
                                pass

                    new_inv = InventoryItem(
                        sku=promo_sku,
                        name=staging_item.name,
                        set_name=staging_item.set_name,
                        sequence_number=staging_item.sequence_number,
                        cost=cost,
                        price=staging_item.market_price,
                        shop_listing_price=calc_shop_price,
                        sticker_price=staging_item.suggested_price,
                        card_type=staging_item.card_type,
                        variant=staging_item.variant,
                        condition=staging_item.condition,
                        stock=staging_item.quantity if staging_item.quantity else 1,
                        image_url=staging_item.image_path,
                        custom_image_url=staging_item.image_path
                    )
                    db_session.add(new_inv)
                    new_purchase = PurchaseRecord(sku=new_inv.sku, quantity=new_inv.stock, cost_per_unit=cost)
                    db_session.add(new_purchase)

                    remove_signature_from_cache(
                        staging_item.name or "", 
                        staging_item.set_name or "", 
                        staging_item.sequence_number or "",
                        staging_item.variant or "",
                        staging_item.condition or ""
                    )
                    db_session.delete(staging_item)
                    db_session.flush()
                    generate_item_barcode(new_inv.sku, format=self.label_format_var.get())

                success_count += 1
            except Exception as e:
                print(f"[!] Promotion Error: {e}")
                error_count += 1

        try:
            db_session.commit()
            messagebox.showinfo("Batch Committed", f"Committed {success_count} cards to inventory. Errors: {error_count}")
        except Exception as e:
            db_session.rollback()
            messagebox.showerror("Error", f"Failed to commit batch: {e}")

        self.refresh_staging_dock()
        self.update_callback()

    def clear_staging(self):
        if messagebox.askyesno("Confirm", "Clear all items in staging queue?"):
            db_session.query(StagingItem).delete()
            db_session.commit()
            clear_signatures_cache()
            self.refresh_staging_dock()
            self.update_callback()

    def apply_pending_trades(self):
        """Open a dialog listing pending PendingTrade records; apply selected ones."""
        pending = db_session.query(PendingTrade).filter_by(status='pending').all()
        if not pending:
            messagebox.showinfo("No Pending Trades",
                                "There are no pending trades to apply. "
                                "Add placeholder trades first via Checkout or Live POS.")
            return
        ApplyTradesDialog(self, pending, on_confirm=self._do_apply_trades)

    def _do_apply_trades(self, selected_ids):
        if not selected_ids:
            messagebox.showwarning("Nothing Selected", "No trades were selected.")
            return
        success, msg = apply_trade_values_to_staging(selected_ids)
        if success:
            messagebox.showinfo("Applied Successfully", msg)
            self.refresh_staging_dock()
            self.update_callback()
        else:
            messagebox.showerror("Apply Failed", msg)


class ApplyTradesDialog(ctk.CTkToplevel):
    """Dialog showing pending trades with checkboxes to select which to apply."""
    def __init__(self, master, pending_trades, on_confirm):
        super().__init__(master)
        self.title("Apply Trade Values to Staging")
        self.geometry("500x400")
        self.resizable(False, True)
        self.transient(master)
        self.grab_set()
        self._pending = pending_trades
        self._on_confirm = on_confirm
        self._checks = []
        self._build_ui()

    def _build_ui(self):
        self.configure(fg_color="#121212")
        ctk.CTkLabel(self, text="💰 SELECT TRADES TO APPLY",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#D97706").pack(pady=(16, 6), padx=20, anchor="w")

        ctk.CTkLabel(self,
                     text="Selected trade costs will be distributed proportionally by market\n"
                          "value across all staging items and promoted to inventory.",
                     font=ctk.CTkFont(size=11), text_color="#A1A1AA",
                     justify="left").pack(padx=20, anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=10)

        for trade in self._pending:
            var = tk.BooleanVar(value=True)
            self._checks.append((trade.id, var))
            row = ctk.CTkFrame(scroll, fg_color="#1E1E1E", corner_radius=6)
            row.pack(fill="x", pady=3, padx=4)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkCheckBox(row, variable=var, text="", width=24).grid(row=0, column=0, padx=8, pady=8)
            ts = trade.timestamp.strftime("%Y-%m-%d %H:%M") if trade.timestamp else "?"
            ctk.CTkLabel(row,
                         text=f"Mkt: ${trade.total_market_value:.2f}  →  Cash: ${trade.total_cash_paid:.2f}",
                         anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#FFFFFF").grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(row, text=ts, text_color="#666666",
                         font=ctk.CTkFont(size=10)).grid(row=0, column=2, padx=10)
            ctk.CTkButton(row, text="✕", width=24, height=24, fg_color="#944747", hover_color="#7A3A3A",
                          command=lambda t=trade, r=row: self._clear_trade(t, r)).grid(row=0, column=3, padx=(0, 10))

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=12)
        ctk.CTkButton(btn_f, text="✅ Apply Selected", fg_color="#D97706", hover_color="#B45309",
                      width=160, command=self._confirm).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="#444444", width=100,
                      command=self.destroy).pack(side="left", padx=8)

    def _clear_trade(self, trade, row_frame):
        if messagebox.askyesno("Clear Credit", f"Are you sure you want to clear this pending trade credit (${trade.total_cash_paid:.2f})?"):
            try:
                trade_id = trade.id
                db_session.delete(trade)
                db_session.commit()
                row_frame.destroy()
                self._checks = [(tid, var) for tid, var in self._checks if tid != trade_id]
                if not self._checks:
                    messagebox.showinfo("No Pending Trades", "All pending trade credits have been cleared.")
                    self.destroy()
            except Exception as e:
                db_session.rollback()
                messagebox.showerror("Error", f"Failed to clear trade credit: {e}")

    def _confirm(self):
        selected = [tid for tid, var in self._checks if var.get()]
        self.destroy()
        self._on_confirm(selected)


class ActionFrame(ctk.CTkFrame):
    def __init__(self, master, commit_callback):
        super().__init__(master, fg_color="#16161A", border_width=1, border_color="#1F1F23", corner_radius=8)
        self.commit_callback = commit_callback
        self.setup_ui()

    def setup_ui(self):
        info_sub_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_sub_frame.pack(side="left", padx=20, pady=12)

        self.total_cards_lbl = ctk.CTkLabel(info_sub_frame, text="Session Total Cards: 0", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#E4E4E7")
        self.total_cards_lbl.pack(anchor="w")

        self.total_value_lbl = ctk.CTkLabel(info_sub_frame, text="Session Total Value: $0.00", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#10B981")
        self.total_value_lbl.pack(anchor="w")

        self.commit_btn = ctk.CTkButton(self, text="🚀 COMMIT BATCH TO INVENTORY", height=38, width=240, fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), command=self.commit_callback)
        self.commit_btn.pack(side="right", padx=20, pady=12)

    def update_totals(self):
        items = db_session.query(StagingItem).all()
        total_cards = sum(item.quantity for item in items)
        total_val = sum((item.market_price or 0.0) * (item.quantity or 1) for item in items)

        self.total_cards_lbl.configure(text=f"Session Total Cards: {total_cards}")
        self.total_value_lbl.configure(text=f"Session Total Value: ${total_val:.2f}")



from database import OnlinePullQueue

class ReviewSyncFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback=None):
        super().__init__(master, fg_color="#09090B")
        self.refresh_callback = refresh_callback
        
        header = ctk.CTkFrame(self, fg_color="#18181B", height=60)
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(header, text="REVIEW & SYNC STAGING", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=15)
        
        # Pagination state
        self.current_page = 1
        self.items_per_page = 10

        # Filter Frame (Search, Sort, Tabs)
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.filter_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(self.filter_frame, placeholder_text="Filter by Name, SKU, or Set...", height=35, border_color="#333333")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", lambda e: self.reset_page_and_refresh())
        
        self.sort_var = ctk.StringVar(value="Newest First")
        self.sort_dropdown = ctk.CTkOptionMenu(
            self.filter_frame, 
            variable=self.sort_var, 
            values=["Newest First", "Price (High-Low)", "Price (Low-High)", "Name (A-Z)", "Set (A-Z)", "Missing Image"],
            command=lambda v: self.reset_page_and_refresh(),
            button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00"
        )
        self.sort_dropdown.grid(row=0, column=1, sticky="e", padx=(0, 5))
        
        self.filter_var = ctk.StringVar(value="All")
        self.seg_btn = ctk.CTkSegmentedButton(self.filter_frame, values=["All", "Singles", "Graded", "Sealed"], variable=self.filter_var, command=lambda v: self.reset_page_and_refresh())
        self.seg_btn.grid(row=0, column=2, sticky="e")

        # Pagination Controls Frame
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.pack(fill="x", padx=20, pady=(0, 5))
        self.pagination_frame.grid_columnconfigure(1, weight=1)

        self.prev_btn = ctk.CTkButton(self.pagination_frame, text="⬅️ Previous", width=100, command=self.prev_page)
        self.prev_btn.grid(row=0, column=0, sticky="w")

        self.page_lbl = ctk.CTkLabel(self.pagination_frame, text="Page 1 of 1", font=ctk.CTkFont(weight="bold"))
        self.page_lbl.grid(row=0, column=1, padx=10)

        self.next_btn = ctk.CTkButton(self.pagination_frame, text="Next ➡️", width=100, command=self.next_page)
        self.next_btn.grid(row=0, column=2, sticky="e", padx=(0, 5))
        
        self.last_btn = ctk.CTkButton(self.pagination_frame, text="Last ⏭️", width=100, command=self.last_page)
        self.last_btn.grid(row=0, column=3, sticky="e")
        
        self.load_img_btn = ctk.CTkButton(self.pagination_frame, text="🖼️ Load All Images", width=120, command=self.load_all_images)
        self.load_img_btn.grid(row=0, column=4, padx=20, sticky="e")
        
        self.recalc_btn = ctk.CTkButton(self.pagination_frame, text="🔄 Recalculate Prices", width=140, command=self.recalculate_prices)
        self.recalc_btn.grid(row=0, column=5, padx=(0, 20), sticky="e")
        
        self.verify_btn = ctk.CTkButton(self.pagination_frame, text="🔍 Verify Shopify Status", width=160, fg_color="#F59E0B", hover_color="#D97706", command=self.verify_shopify_status)
        self.verify_btn.grid(row=0, column=6, padx=(0, 20), sticky="e")
        
        self.approve_all_btn = ctk.CTkButton(self.pagination_frame, text="✅ Approve Page", width=120, fg_color="#10B981", hover_color="#059669", command=self.approve_current_page)
        self.approve_all_btn.grid(row=0, column=7, sticky="e", padx=(0, 5))
        
        self.send_batch_btn = ctk.CTkButton(self.pagination_frame, text="🚀 Send Batch", width=120, fg_color="#8B5CF6", hover_color="#7C3AED", command=self.send_batch)
        self.send_batch_btn.grid(row=0, column=8, sticky="e")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.after(100, self.refresh_list)

    def reset_page_and_refresh(self):
        self.current_page = 1
        self.refresh_list()

    def verify_shopify_status(self):
        from tkinter import messagebox
        import threading
        from database import db_session, InventoryItem
        from services.shopify_client import ShopifyClient
        
        self.verify_btn.configure(state="disabled", text="Verifying...")
        
        def _worker():
            try:
                client = ShopifyClient()
                variants = client.fetch_all_variants()
                active_skus = {k: v['inventory_quantity'] for k, v in variants.items()}
                
                # Find local items that think they are synced
                synced_items = db_session.query(InventoryItem).filter(InventoryItem.sync_status.in_(['synced', 'active'])).all()
                flagged_count = 0
                
                for item in synced_items:
                    if item.sku and item.sku not in active_skus:
                        # Card was deleted on Shopify! Move back to paused/review.
                        item.sync_status = 'paused'
                        item.needs_update = True
                        flagged_count += 1
                    elif item.sku and item.sku in active_skus:
                        # Card exists, check quantity
                        shopify_qty = active_skus[item.sku]
                        needs_stock_update = item.stock != shopify_qty
                        
                        shop_var = variants[item.sku]
                        shop_has_images = shop_var.get('has_images', False)
                        
                        local_img = getattr(item, 'custom_image_url', None) or getattr(item, 'image_url', None)
                        import os
                        has_valid_img = local_img and (str(local_img).startswith('http') or os.path.exists(local_img))
                        needs_image_update = has_valid_img and not shop_has_images
                        
                        from database import SyncOutbox
                        if needs_image_update:
                            print(f"[*] Missing Image detected for {item.sku}. Queued sync.")
                            outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=item.price)
                            db_session.add(outbox)
                        elif needs_stock_update:
                            # Quantity mismatch detected! Queue an overriding stock update.
                            diff = item.stock - shopify_qty
                            outbox = SyncOutbox(action_type='stock_update', sku=item.sku, quantity_change=diff, new_price=0.0)
                            db_session.add(outbox)
                            print(f"[*] Audit Mismatch: {item.sku} (Local: {item.stock}, Shopify: {shopify_qty}). Queued sync.")
                        
                db_session.commit()
                
                def _done():
                    self.verify_btn.configure(state="normal", text="🔍 Verify Shopify Status")
                    self.refresh_list()
                    if self.refresh_callback:
                        self.refresh_callback()
                    messagebox.showinfo("Verification Complete", f"Shopify verification complete.\nFound {flagged_count} local cards that were deleted on Shopify. They have been moved back to Review & Sync.")
                self.after(0, _done)
                
            except Exception as e:
                def _err():
                    self.verify_btn.configure(state="normal", text="🔍 Verify Shopify Status")
                    messagebox.showerror("Verification Failed", f"Failed to verify status: {e}")
                self.after(0, _err)
                
        threading.Thread(target=_worker, daemon=True).start()

    def approve_current_page(self):
        from database import db_session, SyncOutbox
        import threading

        if not hasattr(self, 'current_page_widgets') or not self.current_page_widgets:
            return

        for widget_tuple in self.current_page_widgets:
            i, ne, se, sqe, me, she, ie, sw, qv = widget_tuple
            try:
                i.name = ne.get()
                i.set_name = se.get()
                i.sequence_number = sqe.get()
                i.price = float(me.get())
                i.shop_listing_price = float(she.get())
                i.custom_image_url = ie.get()
                i.paused_stock = i.stock - qv.get()

                # Respect the Live/Paused switch
                if sw.get():
                    i.sync_status = 'approved'
                    outbox = SyncOutbox(action_type='price_update', sku=i.sku, quantity_change=0, new_price=i.shop_listing_price)
                    db_session.add(outbox)
                else:
                    i.sync_status = 'paused'
            except ValueError:
                print(f"Invalid price format for {i.name}")
                continue

        db_session.commit()
        self.refresh_list()

        
    def send_batch(self):
        from database import db_session, InventoryItem
        from services.shopify_client import ShopifyClient
        from tkinter import messagebox
        import threading
        
        items_to_push = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'approved').filter(InventoryItem.stock > 0).all()
        if not items_to_push:
            messagebox.showinfo("Empty Batch", "No approved cards waiting to be sent.")
            return
            
        # Create Progress Modal
        progress_modal = ctk.CTkToplevel(self)
        progress_modal.title("Sending Batch to Shopify...")
        progress_modal.geometry("400x150")
        progress_modal.transient(self.winfo_toplevel())
        progress_modal.grab_set()
        
        lbl = ctk.CTkLabel(progress_modal, text=f"Sending {len(items_to_push)} cards to Shopify. Please wait...", font=ctk.CTkFont(weight="bold"))
        lbl.pack(pady=(20, 10))
        
        progress_bar = ctk.CTkProgressBar(progress_modal, width=300, progress_color="#8B5CF6")
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        pct_lbl = ctk.CTkLabel(progress_modal, text=f"0% (0/{len(items_to_push)})")
        pct_lbl.pack()
        
        self.send_batch_btn.configure(state="disabled", text="Pushing...")
        
        def _push_batch_worker():
            client = ShopifyClient()
            total = len(items_to_push)
            success_count = 0
            
            for idx, i in enumerate(items_to_push, 1):
                data = {
                    'name': i.name, 'set_name': i.set_name, 'sequence_number': i.sequence_number,
                    'sku': i.sku, 'market_price': i.price, 'shop_listing_price': i.shop_listing_price,
                    'condition': i.condition, 'card_type': i.card_type,
                    'custom_image_url': i.custom_image_url, 'image_url': i.image_url,
                    'quantity': max(0, i.stock - (getattr(i, 'paused_stock', 0) or 0)),
                    'game': getattr(i, 'game', 'Pokemon')
                }
                success, msg = client.create_or_update_product(data)
                if success:
                    i.sync_status = 'active'
                    success_count += 1
                else:
                    print(f"Push failed for {i.name}: {msg}")
                    
                # Safely update progress bar
                def _update_ui(current=idx):
                    progress = current / total if total > 0 else 0
                    progress_bar.set(progress)
                    pct_lbl.configure(text=f"{int(progress * 100)}% ({current}/{total})")
                self.after(0, _update_ui)
            
            db_session.commit()
            
            def _reset_ui():
                self.send_batch_btn.configure(state="normal", text="🚀 Send Batch")
                progress_modal.destroy()
                messagebox.showinfo("Batch Complete", f"Successfully pushed {success_count} out of {total} cards to Shopify.")
                self.refresh_list()
                
            self.after(0, _reset_ui)
            
        threading.Thread(target=_push_batch_worker, daemon=True).start()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_list()

    def next_page(self):
        from database import db_session, InventoryItem
        total_items = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'paused').filter(InventoryItem.stock > 0).count()
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_list()

    def last_page(self):
        from database import db_session, InventoryItem
        total_items = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'paused').filter(InventoryItem.stock > 0).count()
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page
        if total_pages > 0 and self.current_page != total_pages:
            self.current_page = total_pages
            self.refresh_list()

    def recalculate_prices(self):
        from database import db_session, InventoryItem
        from logic import calculate_shop_price
        
        items = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'paused').filter(InventoryItem.stock > 0).all()
        for item in items:
            item.shop_listing_price = calculate_shop_price(item.price)
            
        db_session.commit()
        self.refresh_list()

    def load_all_images(self):
        import threading
        from database import db_session, InventoryItem
        import os
        
        # Disable button while loading to prevent spam
        self.load_img_btn.configure(state="disabled", text="LOADING...")
        
        def fetch_all_worker():
            try:
                items = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'paused').filter(InventoryItem.stock > 0).all()
                import requests, PIL.Image, PIL.ImageOps
                from io import BytesIO
                
                for item in items:
                    img_url = item.custom_image_url or item.image_url
                    if not img_url or not img_url.startswith('http'):
                        continue
                        
                    thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")
                    
                    if not os.path.exists(thumb_path):
                        try:
                            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                            resp = requests.get(img_url, timeout=5)
                            if resp.status_code == 200:
                                downloaded_img = PIL.Image.open(BytesIO(resp.content))
                                if downloaded_img.mode != 'RGB':
                                    downloaded_img = downloaded_img.convert('RGB')
                                downloaded_img.save(thumb_path)
                                
                                # If this item is currently on screen, update it dynamically
                                if hasattr(self, 'current_page_labels'):
                                    for screen_item, lbl in self.current_page_labels:
                                        if screen_item.id == item.id:
                                            # Create ctk image
                                            img_for_ui = PIL.ImageOps.pad(downloaded_img.copy(), (120, 168), color="#18181B")
                                            photo = ctk.CTkImage(light_image=img_for_ui, dark_image=img_for_ui, size=(120, 168))
                                            def update_lbl(target_lbl=lbl, p=photo):
                                                try:
                                                    target_lbl.configure(image=p, text="")
                                                    target_lbl.image = p
                                                except Exception:
                                                    pass
                                            lbl.after(0, update_lbl)
                        except Exception as e:
                            print(f"Failed to fetch {img_url}: {e}")
            finally:
                # Re-enable button when done
                def restore_btn():
                    try:
                        self.load_img_btn.configure(state="normal", text="🖼️ Load All Images")
                    except Exception:
                        pass
                self.after(0, restore_btn)
                
        threading.Thread(target=fetch_all_worker, daemon=True).start()

    def refresh_list(self):
        for w in self.scroll.winfo_children():
            w.destroy()
            
        from database import db_session, InventoryItem
        from logic import calculate_shop_price
        
        query = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""
        active_tab = self.filter_var.get() if hasattr(self, 'filter_var') else "All"
        sort_choice = self.sort_var.get() if hasattr(self, 'sort_var') else "Newest First"

        base_query = db_session.query(InventoryItem).filter(InventoryItem.sync_status == 'paused').filter(InventoryItem.stock > 0)
        
        if query:
            base_query = base_query.filter(
                (InventoryItem.name.ilike(f"%{query}%")) | 
                (InventoryItem.sku.ilike(f"%{query}%")) | 
                (InventoryItem.set_name.ilike(f"%{query}%"))
            )
            
        if active_tab == "Singles":
            base_query = base_query.filter((InventoryItem.card_type != 'Sealed') & (InventoryItem.card_type != 'Graded') | (InventoryItem.card_type == None))
        elif active_tab == "Sealed":
            base_query = base_query.filter(InventoryItem.card_type == 'Sealed')
        elif active_tab == "Graded":
            base_query = base_query.filter(InventoryItem.card_type == 'Graded')
            
        if sort_choice == "Missing Image":
            base_query = base_query.filter((InventoryItem.image_url == None) | (InventoryItem.image_url == ""))
            base_query = base_query.order_by(InventoryItem.date_added.desc())
        elif sort_choice == "Price (High-Low)":
            base_query = base_query.order_by(InventoryItem.price.desc())
        elif sort_choice == "Price (Low-High)":
            base_query = base_query.order_by(InventoryItem.price.asc())
        elif sort_choice == "Name (A-Z)":
            base_query = base_query.order_by(InventoryItem.name.asc())
        elif sort_choice == "Set (A-Z)":
            base_query = base_query.order_by(InventoryItem.set_name.asc())
        else:
            base_query = base_query.order_by(InventoryItem.date_added.desc())

        items = base_query.all()
        
        total_pages = (len(items) + self.items_per_page - 1) // self.items_per_page
        if total_pages == 0: total_pages = 1
        
        if self.current_page > total_pages:
            self.current_page = total_pages
            
        self.page_lbl.configure(text=f"Page {self.current_page} of {total_pages}")
        
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = items[start_idx:end_idx]
        
        self.current_page_labels = []
        self.current_page_widgets = []

        for item in page_items:
            row = ctk.CTkFrame(self.scroll, fg_color="#18181B", border_width=1, border_color="#27272A", corner_radius=8)
            row.pack(fill="x", pady=5, padx=5)
            row.grid_columnconfigure(2, weight=1)  # Name column expands

            # --- Col 0: Thumbnail ---
            lbl = ctk.CTkLabel(row, text="LOADING", width=120, height=168, fg_color="#27272A")
            lbl.grid(row=0, column=0, rowspan=4, padx=15, pady=15)

            img_url = item.custom_image_url or item.image_url
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{item.sku}.png")

            actual_path_to_load = None
            if item.custom_image_url and os.path.exists(item.custom_image_url):
                actual_path_to_load = item.custom_image_url
            elif os.path.exists(thumb_path):
                actual_path_to_load = thumb_path

            if actual_path_to_load:
                try:
                    import PIL.Image, PIL.ImageOps
                    img = PIL.Image.open(actual_path_to_load)
                    img = PIL.ImageOps.pad(img, (120, 168), color="#18181B")
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 168))
                    lbl.configure(image=photo, text="")
                    lbl.image = photo
                except Exception:
                    lbl.configure(text="NO IMG")
            elif img_url and img_url.startswith('http'):
                lbl.configure(text="URL IMG\n(Click Load)")
            else:
                lbl.configure(text="NO IMG")

            self.current_page_labels.append((item, lbl))

            # --- Col 1: Labels (right-aligned) ---
            ctk.CTkLabel(row, text="Name:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, sticky="e", padx=(10, 4), pady=2)
            ctk.CTkLabel(row, text="Set:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=1, sticky="e", padx=(10, 4), pady=2)
            ctk.CTkLabel(row, text="No:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=1, sticky="e", padx=(10, 4), pady=2)
            ctk.CTkLabel(row, text="Cond:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=3, column=1, sticky="e", padx=(10, 4), pady=2)

            # --- Col 2: Editable text fields ---
            name_ent = ctk.CTkEntry(row, width=200)
            name_ent.insert(0, item.name or "")
            name_ent.grid(row=0, column=2, sticky="w", padx=4, pady=2)

            set_ent = ctk.CTkEntry(row, width=200)
            set_ent.insert(0, item.set_name or "")
            set_ent.grid(row=1, column=2, sticky="w", padx=4, pady=2)

            seq_ent = ctk.CTkEntry(row, width=80)
            seq_ent.insert(0, item.sequence_number or "")
            seq_ent.grid(row=2, column=2, sticky="w", padx=4, pady=2)

            # Condition & Qty (read-only display)
            ctk.CTkLabel(row, text=item.condition or "N/A", font=ctk.CTkFont(size=12)).grid(row=3, column=2, sticky="w", padx=4, pady=2)

            # --- Col 3: Price labels ---
            ctk.CTkLabel(row, text="Market $:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=3, sticky="e", padx=(12, 4), pady=2)
            ctk.CTkLabel(row, text="Shop $:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981").grid(row=1, column=3, sticky="e", padx=(12, 4), pady=2)
            ctk.CTkLabel(row, text="Img URL:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=3, sticky="e", padx=(12, 4), pady=2)
            ctk.CTkLabel(row, text="Qty:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=3, column=3, sticky="e", padx=(12, 4), pady=2)

            # --- Col 4: Price entries ---
            calc_shop_price = calculate_shop_price(item.price or 0.0)
            current_shop_price = item.shop_listing_price if hasattr(item, 'shop_listing_price') and item.shop_listing_price is not None and item.shop_listing_price > 0 else calc_shop_price

            mkt_var = tk.StringVar(value=f"{item.price:.2f}" if item.price else "0.00")
            shop_var = tk.StringVar(value=f"{current_shop_price:.2f}")

            mkt_ent = ctk.CTkEntry(row, width=80, textvariable=mkt_var)
            mkt_ent.grid(row=0, column=4, sticky="w", padx=4, pady=2)

            shop_ent = ctk.CTkEntry(row, width=80, textvariable=shop_var)
            shop_ent.grid(row=1, column=4, sticky="w", padx=4, pady=2)

            def update_shop_price(*args, m_var=mkt_var, s_var=shop_var):
                try:
                    val = float(m_var.get() or 0.0)
                    new_shop = calculate_shop_price(val)
                    s_var.set(f"{new_shop:.2f}")
                except ValueError:
                    pass
            mkt_var.trace_add("write", update_shop_price)

            img_ent = ctk.CTkEntry(row, width=180)
            if item.custom_image_url or item.image_url:
                img_ent.insert(0, item.custom_image_url or item.image_url)
            img_ent.grid(row=2, column=4, sticky="w", padx=4, pady=2)

            ctk.CTkLabel(row, text=str(item.stock), font=ctk.CTkFont(size=12)).grid(row=3, column=4, sticky="w", padx=4, pady=2)

            # --- Col 5: Live / Paused Toggle & Smart Quantity Selector ---
            toggle_frame = ctk.CTkFrame(row, fg_color="transparent")
            toggle_frame.grid(row=0, column=5, rowspan=4, padx=(16, 8), pady=8, sticky="ns")

            is_live = item.sync_status in ('active', 'synced', 'approved')
            live_switch = ctk.CTkSwitch(
                toggle_frame,
                text="Live" if is_live else "Paused",
                width=80,
                progress_color="#10B981",
                button_color="#FFFFFF",
                font=ctk.CTkFont(size=11, weight="bold")
            )
            if is_live:
                live_switch.select()
            else:
                live_switch.deselect()
            live_switch.pack(pady=4)

            # Smart visual quantity selector for multi-stock items
            qty_var = tk.IntVar(value=max(0, item.stock - (getattr(item, 'paused_stock', 0) or 0)))
            
            if item.stock > 1:
                smart_sub_frame = ctk.CTkFrame(toggle_frame, fg_color="#27272A", corner_radius=6)
                smart_sub_frame.pack(pady=(5, 0), fill="x")
                
                lbl_status = ctk.CTkLabel(smart_sub_frame, text=f"{qty_var.get()} Live | {item.stock - qty_var.get()} Paused", font=ctk.CTkFont(size=10, weight="bold"), text_color="#F59E0B" if (item.stock - qty_var.get()) > 0 else "#10B981")
                lbl_status.pack(pady=(2, 2))
                
                btn_sub_frame = ctk.CTkFrame(smart_sub_frame, fg_color="transparent")
                btn_sub_frame.pack(pady=(0, 4))
                
                def dec_qty(qv=qty_var, tot=item.stock, lbl=lbl_status, it=item):
                    if qv.get() > 0:
                        qv.set(qv.get() - 1)
                        paused = tot - qv.get()
                        it.paused_stock = paused
                        lbl.configure(text=f"{qv.get()} Live | {paused} Paused", text_color="#F59E0B" if paused > 0 else "#10B981")
                        db_session.commit()
                        
                def inc_qty(qv=qty_var, tot=item.stock, lbl=lbl_status, it=item):
                    if qv.get() < tot:
                        qv.set(qv.get() + 1)
                        paused = tot - qv.get()
                        it.paused_stock = paused
                        lbl.configure(text=f"{qv.get()} Live | {paused} Paused", text_color="#F59E0B" if paused > 0 else "#10B981")
                        db_session.commit()
                        
                ctk.CTkButton(btn_sub_frame, text="➖", width=24, height=20, fg_color="#374151", hover_color="#1F2937", command=dec_qty).pack(side="left", padx=2)
                ctk.CTkButton(btn_sub_frame, text="➕", width=24, height=20, fg_color="#374151", hover_color="#1F2937", command=inc_qty).pack(side="left", padx=2)
                
                def switch_toggle(qv=qty_var, tot=item.stock, lbl=lbl_status, it=item, sw=live_switch):
                    if sw.get():
                        sw.configure(text="Live")
                        if qv.get() == 0:
                            qv.set(tot)
                            it.paused_stock = 0
                    else:
                        sw.configure(text="Paused")
                        qv.set(0)
                        it.paused_stock = tot
                    paused = tot - qv.get()
                    lbl.configure(text=f"{qv.get()} Live | {paused} Paused", text_color="#F59E0B" if paused > 0 else "#10B981")
                    db_session.commit()
                
                live_switch.configure(command=switch_toggle)
            else:
                def simple_toggle(sw=live_switch, it=item):
                    if sw.get():
                        sw.configure(text="Live")
                        it.paused_stock = 0
                    else:
                        sw.configure(text="Paused")
                        it.paused_stock = 1
                    db_session.commit()
                live_switch.configure(command=simple_toggle)

            # --- Col 6: Action buttons ---
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=6, rowspan=4, padx=(8, 15), pady=8, sticky="ns")

            def push_live(i=item, ne=name_ent, se=set_ent, sqe=seq_ent, me=mkt_ent, she=shop_ent, ie=img_ent, sw=live_switch, qv=qty_var):
                try:
                    i.name = ne.get()
                    i.set_name = se.get()
                    i.sequence_number = sqe.get()
                    i.price = float(me.get())
                    i.shop_listing_price = float(she.get())
                    i.custom_image_url = ie.get()
                    i.paused_stock = i.stock - qv.get()
                    db_session.commit()
                except ValueError:
                    print("Invalid price format")
                    return

                go_live = bool(sw.get())
                qty_to_push = qv.get() if go_live else 0

                from services.shopify_client import ShopifyClient
                import threading
                def _push():
                    client = ShopifyClient()
                    data = {
                        'name': i.name, 'set_name': i.set_name, 'sequence_number': i.sequence_number,
                        'sku': i.sku, 'market_price': i.price, 'shop_listing_price': i.shop_listing_price,
                        'condition': i.condition, 'card_type': i.card_type,
                        'custom_image_url': i.custom_image_url, 'image_url': i.image_url,
                        'quantity': qty_to_push,
                        'game': getattr(i, 'game', 'Pokemon')
                    }
                    success, msg = client.create_or_update_product(data)
                    if success:
                        i.sync_status = 'synced' if go_live else 'paused'
                        db_session.commit()
                        self.after(0, self.refresh_list)
                    else:
                        print(f"Push failed: {msg}")
                threading.Thread(target=_push, daemon=True).start()

            ctk.CTkButton(
                btn_frame, text="🚀 Push", width=90, height=36,
                fg_color="#10B981", hover_color="#059669",
                command=push_live
            ).pack(pady=(0, 6))

            def discard_item(i=item):
                from tkinter import messagebox
                if messagebox.askyesno("Discard", f"Remove '{i.name}' from Review & Sync?\nThis does NOT delete it from Shopify."):
                    i.sync_status = 'paused'
                    db_session.commit()
                    self.refresh_list()

            ctk.CTkButton(
                btn_frame, text="⏸ Skip", width=90, height=36,
                fg_color="#374151", hover_color="#1F2937",
                command=discard_item
            ).pack()

            self.current_page_widgets.append((item, name_ent, set_ent, seq_ent, mkt_ent, shop_ent, img_ent, live_switch, qty_var))


class SoldOnlineFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback=None):
        super().__init__(master, fg_color="#09090B")
        self.refresh_callback = refresh_callback
        
        header = ctk.CTkFrame(self, fg_color="#18181B", height=60)
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(header, text="SOLD ONLINE (CONVENTION PULL LIST)", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=15)
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.refresh_list()

    def refresh_list(self):
        for w in self.scroll.winfo_children():
            w.destroy()
            
        items = db_session.query(OnlinePullQueue).filter(OnlinePullQueue.status == 'pending_pull').all()
        
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="#18181B", border_width=1, border_color="#27272A", corner_radius=8)
            row.pack(fill="x", padx=20, pady=10)
            
            # Lookup inventory info
            inv = db_session.query(InventoryItem).filter_by(sku=item.sku).first()
            if inv:
                card_name = inv.name
                set_name = inv.set_name
                seq = inv.sequence_number
                cond = inv.condition
            else:
                card_name = "Unknown"
                set_name = "Unknown"
                seq = "???"
                cond = "Unknown"
            
            info = f"{card_name} - {set_name} ({seq})"
            ctk.CTkLabel(row, text=info, font=ctk.CTkFont(size=16, weight="bold"), anchor="w").pack(side="left", padx=15, pady=15)
            
            ctk.CTkLabel(row, text=f"Condition: {cond}", font=ctk.CTkFont(size=14), text_color="#A1A1AA").pack(side="left", padx=20)
            ctk.CTkLabel(row, text=f"Order: {item.order_id}", font=ctk.CTkFont(size=14), text_color="#6366F1").pack(side="left", padx=20)
            
            def mark_pulled(i=item):
                i.status = 'pulled'
                # Do NOT decrement stock here, the background poller already removes it locally.
                db_session.commit()
                self.refresh_list()
                
            ctk.CTkButton(row, text="✅ Mark as Pulled", fg_color="#10B981", hover_color="#059669", command=mark_pulled).pack(side="right", padx=20)

class NotificationToast(ctk.CTkToplevel):
    def __init__(self, master, item):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("400x120+40+40")  # Top right ish or top left
        self.configure(fg_color="#FF3B30") # Red banner
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(self, fg_color="#FF3B30", corner_radius=10, border_width=2, border_color="#FFFFFF")
        frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        ctk.CTkLabel(frame, text="⚠️ SHOPIFY SALE - PULL CARD IMMEDIATE", font=APP_FONT_BOLD_LG, text_color="#FFFFFF").pack(pady=(10, 5))
        
        info = f"{item.get('card_name', 'Unknown')} - {item.get('set_name', 'Unknown')} ({item.get('sequence_number', 'Unknown')}) - {item.get('condition', 'Unknown')}"
        ctk.CTkLabel(frame, text=info, font=APP_FONT, text_color="#FFFFFF").pack(pady=5)
        
        ctk.CTkButton(frame, text="OK", width=80, height=30, fg_color="#FFFFFF", text_color="#FF3B30", font=APP_FONT_BOLD_LG, command=self.destroy).pack(pady=10)
        
        # Auto position top right
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        self.geometry(f"+{(screen_width - 420)}+40")
        
        # Play system sound to grab attention
        self.bell()


class IntakeStudioFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # PanedWindow allows adjustable columns
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, bd=0, sashwidth=8, bg="#1F1F23")
        self.paned_window.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="nsew")

        # Left side: Manual Intake is the sole intake view
        self.manual_intake = ManualIntakeFrame(self.paned_window, self.on_card_added)
        self.paned_window.add(self.manual_intake, minsize=320, stretch="always")

        # Right staging dock
        self.staging_dock = StagingDockFrame(self.paned_window, self.on_staging_updated)
        self.paned_window.add(self.staging_dock, minsize=400, stretch="always")

        # Set initial sash position (roughly 35% intake form / 65% dock)
        self.after(100, lambda: self.paned_window.sash_place(0, int(self.winfo_width() * 0.35), 0))

        # Spanning bottom bar
        self.action_bar = ActionFrame(self, self.staging_dock.commit_batch)
        self.action_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        self.refresh_staging_dock()

    def on_card_added(self, card_data=None):
        self.refresh_staging_dock()
        self.refresh_callback()

    def on_staging_updated(self):
        self.refresh_staging_dock()
        self.refresh_callback()

    def refresh_staging_dock(self):
        self.staging_dock.refresh_staging_dock()
        self.action_bar.update_totals()


class CashSaleConfirmationModal(ctk.CTkToplevel):
    def __init__(self, master, cart_items, total_neg, total_cost, on_confirm_callback):
        super().__init__(master)
        self.title("Confirm Cash Sale")
        self.geometry("450x450")
        self.transient(master)
        self.grab_set()

        self.cart_items = cart_items
        self.total_neg = total_neg
        self.total_cost = total_cost
        self.on_confirm_callback = on_confirm_callback
        
        self.setup_ui()
        
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="FINAL SALE CONFIRMATION", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10))
        
        frame = ctk.CTkFrame(self, fg_color="#1A1A1A")
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Haggling / Final Sale Price
        price_frame = ctk.CTkFrame(frame, fg_color="transparent")
        price_frame.pack(fill="x", pady=5, padx=20)
        ctk.CTkLabel(price_frame, text="Final Sale Price: $", font=ctk.CTkFont(size=16)).pack(side="left")
        
        self.sale_price_var = tk.StringVar(value=f"{self.total_neg:.2f}")
        self.sale_price_var.trace_add("write", self.update_calculations)
        ctk.CTkEntry(price_frame, textvariable=self.sale_price_var, width=100).pack(side="left", padx=5)

        # Amount Tendered
        tender_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tender_frame.pack(fill="x", pady=5, padx=20)
        ctk.CTkLabel(tender_frame, text="Amount Tendered: $", font=ctk.CTkFont(size=16)).pack(side="left")
        
        self.tendered_var = tk.StringVar(value="")
        self.tendered_var.trace_add("write", self.update_calculations)
        self.tender_entry = ctk.CTkEntry(tender_frame, textvariable=self.tendered_var, width=100)
        self.tender_entry.pack(side="left", padx=5)
        self.tender_entry.focus()
        
        # Info Readouts
        self.cost_lbl = ctk.CTkLabel(frame, text=f"Total Cost Basis: ${self.total_cost:.2f}", font=ctk.CTkFont(size=14))
        self.cost_lbl.pack(pady=5)
        
        self.profit_lbl = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.profit_lbl.pack(pady=5)
        
        self.change_lbl = ctk.CTkLabel(frame, text="Change Due: $0.00", font=ctk.CTkFont(size=20, weight="bold"), text_color="#f39c12")
        self.change_lbl.pack(pady=15)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        self.confirm_btn = ctk.CTkButton(btn_frame, text="✅ Confirm Sale", fg_color="#2fa572", height=40, command=self.confirm)
        self.confirm_btn.pack(side="left", expand=True, padx=5)
        ctk.CTkButton(btn_frame, text="❌ Cancel", fg_color="#944747", height=40, command=self.destroy).pack(side="right", expand=True, padx=5)
        
        self.update_calculations()

    def update_calculations(self, *args):
        try:
            sale_price = float(self.sale_price_var.get() or 0)
            net_profit = sale_price - self.total_cost
            prof_color = "#2fa572" if net_profit >= 0 else "#944747"
            self.profit_lbl.configure(text=f"Net Profit: ${net_profit:.2f}", text_color=prof_color)
            
            tendered = float(self.tendered_var.get() or 0)
            change = tendered - sale_price
            if change >= 0 and tendered > 0:
                self.change_lbl.configure(text=f"Change Due: ${change:.2f}", text_color="#2fa572")
            else:
                self.change_lbl.configure(text=f"Change Due: $0.00", text_color="#f39c12")
        except ValueError:
            pass

    def confirm(self):
        try:
            final_price = float(self.sale_price_var.get() or 0)
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Error", "Invalid sale price.")
            return
            
        from logic import finalize_sale
        success = finalize_sale(self.cart_items, final_price, "Cash")
        if success:
            if self.on_confirm_callback:
                self.on_confirm_callback()
            self.destroy()
        else:
            from tkinter import messagebox
            messagebox.showerror("Error", "Failed to process the sale.")



class SetValidationDialog(ctk.CTkToplevel):
    def __init__(self, master, typed_name, best_match=None):
        super().__init__(master)
        self.title("Set Name Validation")
        self.geometry("500x350")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.result = "cancel"
        self.selected_set_name = typed_name
        self.selected_language = "English"
        
        # Initial view frame
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(self.main_frame, text="⚠️ Unrecognized Set Name", font=ctk.CTkFont(size=20, weight="bold"), text_color="#EAB308").pack(pady=(10, 10))
        ctk.CTkLabel(self.main_frame, text=f"The set '{typed_name}' is not in your database.", font=ctk.CTkFont(size=14)).pack(pady=5)
        
        if best_match:
            ctk.CTkLabel(self.main_frame, text=f"Did you mean '{best_match}'?", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            def use_match():
                self.result = "use_match"
                self.selected_set_name = best_match
                self.grab_release()
                self.destroy()
            ctk.CTkButton(self.main_frame, text=f"✅ Yes, use '{best_match}'", command=use_match, fg_color="#2fa572", height=40).pack(fill="x", pady=5)
            
        def new_set():
            self.selected_set_name = typed_name
            self.show_language_options()
            
        ctk.CTkButton(self.main_frame, text="➕ No, it's a New Set", command=new_set, fg_color="#3b8ed0", height=40).pack(fill="x", pady=5)
        ctk.CTkButton(self.main_frame, text="Cancel", command=self.on_closing, fg_color="#944747", height=40).pack(fill="x", pady=5)
        
        # Language options frame (hidden initially)
        self.lang_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        ctk.CTkLabel(self.lang_frame, text="Select Language for New Set:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.lang_var = ctk.StringVar(self, value="English")
        self.lang_menu = ctk.CTkOptionMenu(self.lang_frame, values=["English", "Japanese", "Chinese"], variable=self.lang_var, height=35, font=ctk.CTkFont(size=14))
        self.lang_menu.pack(pady=15, fill="x", padx=10)
        
        def save_new():
            self.result = "new_set"
            self.selected_language = self.lang_var.get()
            self.grab_release()
            self.destroy()
        ctk.CTkButton(self.lang_frame, text="Save & Continue", command=save_new, fg_color="#2fa572", height=40).pack(fill="x", pady=(15, 5))
        ctk.CTkButton(self.lang_frame, text="Cancel", command=self.on_closing, fg_color="#944747", height=40).pack(fill="x", pady=5)
        
    def on_closing(self):
        self.result = "cancel"
        self.grab_release()
        self.destroy()

    def show_language_options(self):
        self.main_frame.pack_forget()
        self.lang_frame.pack(fill="both", expand=True, padx=20, pady=10)

class ManualIntakeFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback=None, add_callback=None):
        super().__init__(master, fg_color="#09090B")
        self.refresh_callback = refresh_callback
        self.add_callback = add_callback
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(self, fg_color="#18181B", height=60)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="MANUAL INTAKE", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=15)
        
        # Tabview
        self.tabs = ctk.CTkTabview(self, fg_color="#18181B", segmented_button_selected_color="#F2A900", segmented_button_selected_hover_color="#C88A00")
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        self.tab_singles = self.tabs.add("Single Cards")
        self.tab_sealed = self.tabs.add("Sealed")
        
        self._setup_singles_tab()
        self._setup_sealed_tab()

    def _create_row(self, parent, label_text, widget_class, **kwargs):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=label_text, width=150, anchor="e", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        widget = widget_class(row, **kwargs)
        widget.pack(side="left", fill="x", expand=True)
        return row, widget

    def _setup_singles_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_singles, fg_color="transparent")
        container.pack(fill="both", expand=True)
        
        self.game_var = ctk.StringVar(value="Pokemon")
        _, self.game_menu = self._create_row(container, "Game:", ctk.CTkOptionMenu, variable=self.game_var, values=["Pokemon", "One Piece"], button_color="#2fa572", button_hover_color="#268a5f")
        
        _, self.name_ent = self._create_row(container, "Card Name:", ctk.CTkEntry)
        
        set_row = ctk.CTkFrame(container, fg_color="transparent")
        set_row.pack(fill="x", pady=5)
        ctk.CTkLabel(set_row, text="Set Name:", width=150, anchor="e", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.set_ent = ctk.CTkEntry(set_row, border_color="#333333")
        self.set_ent.pack(side="left", fill="x", expand=True)
        
        self.lang_var = ctk.StringVar(value="English")
        self.lang_menu = ctk.CTkOptionMenu(set_row, variable=self.lang_var, values=["English", "Japanese", "Chinese"], width=100, button_color="#F2A900", button_hover_color="#C88A00", dropdown_hover_color="#C88A00")
        self.lang_menu.pack(side="left", padx=(10, 5))
        ctk.CTkButton(set_row, text="Add Set to List", width=120, command=self.add_set_to_list).pack(side="left")
        
        _, self.seq_ent = self._create_row(container, "Card Number:", ctk.CTkEntry)
        _, self.price_ent = self._create_row(container, "Market Price ($):", ctk.CTkEntry)
        
        self.cond_var = ctk.StringVar(value="Near Mint")
        _, self.cond_menu = self._create_row(container, "Condition:", ctk.CTkOptionMenu, variable=self.cond_var, values=["Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged"])
        
        self.var_var = ctk.StringVar(value="Normal")
        _, self.var_menu = self._create_row(container, "Variance:", ctk.CTkOptionMenu, variable=self.var_var, values=["Normal", "Holofoil", "Reverse Holofoil"])
        
        # Graded toggle
        grade_toggle_row = ctk.CTkFrame(container, fg_color="transparent")
        grade_toggle_row.pack(fill="x", pady=10)
        ctk.CTkLabel(grade_toggle_row, text="Graded Card:", width=150, anchor="e", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.is_graded_var = ctk.BooleanVar(value=False)
        self.graded_switch = ctk.CTkSwitch(grade_toggle_row, text="", variable=self.is_graded_var, command=self._toggle_graded_options, progress_color="#F2A900")
        self.graded_switch.pack(side="left")

        # Graded Options (Hidden by default)
        self.graded_options_frame = ctk.CTkFrame(container, fg_color="transparent")
        
        self.grade_company_var = ctk.StringVar(value="PSA")
        _, self.grade_company_menu = self._create_row(self.graded_options_frame, "Company:", ctk.CTkOptionMenu, variable=self.grade_company_var, values=["PSA", "Beckett", "CGC", "TAG", "SGC"])
        
        self.grade_val_var = ctk.StringVar(value="10")
        _, self.grade_val_menu = self._create_row(self.graded_options_frame, "Grade:", ctk.CTkOptionMenu, variable=self.grade_val_var, values=["10", "9.5", "9", "8.5", "8", "7", "6", "5", "4", "3", "2", "1", "Authentic"])
        
        img_row = ctk.CTkFrame(container, fg_color="transparent")
        img_row.pack(fill="x", pady=5)
        ctk.CTkLabel(img_row, text="Image URL (Optional):", width=150, anchor="e", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.img_ent = ctk.CTkEntry(img_row)
        self.img_ent.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(img_row, text="🔄 Refresh Image", width=120, command=lambda: self.refresh_image_preview(self.img_ent.get(), self.img_preview_lbl)).pack(side="left", padx=(10, 0))
        
        self.img_preview_lbl = ctk.CTkLabel(container, text="[ No Image ]")
        self.img_preview_lbl.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=30)
        ctk.CTkButton(btn_frame, text="🗄️ Local DB", height=40, font=ctk.CTkFont(weight="bold"), command=self.local_db_fetch).pack(side="left", expand=True, padx=10)
        ctk.CTkButton(btn_frame, text="🔍 API Fetch", height=40, font=ctk.CTkFont(weight="bold"), command=self.api_fetch).pack(side="left", expand=True, padx=10)
        ctk.CTkButton(btn_frame, text="📥 Send to Staging", height=40, fg_color="#2fa572", font=ctk.CTkFont(weight="bold"), command=self.send_to_staging).pack(side="left", expand=True, padx=10)

    def _toggle_graded_options(self):
        if self.is_graded_var.get():
            self.graded_options_frame.pack(fill="x", after=self.graded_switch.master)
        else:
            self.graded_options_frame.pack_forget()

    def _setup_sealed_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_sealed, fg_color="transparent")
        container.pack(fill="both", expand=True)
        
        self.sealed_game_var = ctk.StringVar(value="Pokemon")
        _, self.sealed_game_menu = self._create_row(container, "Game:", ctk.CTkOptionMenu, variable=self.sealed_game_var, values=["Pokemon", "One Piece"], button_color="#2fa572", button_hover_color="#268a5f")
        
        _, self.sealed_name_ent = self._create_row(container, "Product Name:", ctk.CTkEntry)
        _, self.sealed_set_ent = self._create_row(container, "Set Name:", ctk.CTkEntry)
        _, self.sealed_price_ent = self._create_row(container, "Market Price ($):", ctk.CTkEntry)
        
        img_row = ctk.CTkFrame(container, fg_color="transparent")
        img_row.pack(fill="x", pady=5)
        ctk.CTkLabel(img_row, text="Image URL (Optional):", width=150, anchor="e", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.sealed_img_ent = ctk.CTkEntry(img_row)
        self.sealed_img_ent.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(img_row, text="🔄 Refresh Image", width=120, command=lambda: self.refresh_image_preview(self.sealed_img_ent.get(), self.sealed_img_preview_lbl)).pack(side="left", padx=(10, 0))
        
        self.sealed_img_preview_lbl = ctk.CTkLabel(container, text="[ No Image ]")
        self.sealed_img_preview_lbl.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=30)
        ctk.CTkButton(btn_frame, text="📥 Send to Staging", height=40, fg_color="#2fa572", font=ctk.CTkFont(weight="bold"), command=self.send_sealed_to_staging).pack(side="left", expand=True, padx=10)

    def add_set_to_list(self):
        set_name = self.set_ent.get().strip()
        if not set_name:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Set Name is empty.")
            return
            
        lang = self.lang_var.get()
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_map = {
            "English": "set_names.txt",
            "Japanese": "set_names_ja.txt",
            "Chinese": "set_names_zh.txt"
        }
        path = os.path.join(base_dir, file_map[lang])
        
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write("\n" + set_name)
            from tkinter import messagebox
            messagebox.showinfo("Success", f"Added '{set_name}' to {lang} set list!")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to add set name: {e}")

    def refresh_image_preview(self, url=None, label=None):
        label = label or self.img_preview_lbl
        url = url.strip() if url else ""
        if not url:
            label.configure(image="", text="[ No Image ]")
            return
            
        import requests, threading, io, os
        from PIL import Image, ImageTk
        def _download():
            try:
                if url.startswith('http'):
                    resp = requests.get(url, timeout=5)
                    resp.raise_for_status()
                    img = Image.open(io.BytesIO(resp.content))
                else:
                    if os.path.exists(url):
                        img = Image.open(url)
                    else:
                        raise Exception("Local path does not exist")
                img.thumbnail((200, 280))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.after(0, lambda: label.configure(image=ctk_img, text=""))
                label.image = ctk_img
            except Exception as e:
                self.after(0, lambda: label.configure(image="", text="[ Image Load Failed ]"))
        threading.Thread(target=_download, daemon=True).start()

    def local_db_fetch(self):
        set_name = self.set_ent.get().strip()
        seq = self.seq_ent.get().strip()
        
        if not set_name or not seq:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Set Name and Card Number are required for local DB fetch.")
            return
            
        import sys, os
        img_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image_db_manager')
        if img_db_path not in sys.path:
            sys.path.append(img_db_path)
        import db_handler as img_db_handler
        
        name = self.name_ent.get().strip()
        local_img = img_db_handler.find_image_by_set_and_number(set_name, seq, card_name=name)
        if local_img:
            self._update_ui("", local_img)
        else:
            self._show_error("No matching image found in local DB.")

    def api_fetch(self):
        name = self.name_ent.get().strip()
        set_name = self.set_ent.get().strip()
        seq = self.seq_ent.get().strip()
        
        if not name or not set_name:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Name and Set Name are required for API fetch.")
            return
            
        import threading
        def _fetch():
            from api_client import PokemonAPI
            client = PokemonAPI()
            result = client.fetch_card_data(set_name, seq, card_name=name)
            if result:
                self.after(0, self._update_ui, result.get('market_price', ''), result.get('high_res_image', ''))
            else:
                self.after(0, self._show_error, "No matching card found.")
        
        threading.Thread(target=_fetch, daemon=True).start()
        
    def _update_ui(self, price, img_url):
        # We no longer overwrite the user's manual market price with the API's price
        if img_url:
            self.img_ent.delete(0, 'end')
            self.img_ent.insert(0, img_url)
            self.refresh_image_preview(img_url, self.img_preview_lbl)
            
    def _show_error(self, err):
        from tkinter import messagebox
        messagebox.showerror("API Error", f"Could not find match:\n{err}")

    def _process_image_download(self, img_val):
        local_img_path = None
        target_sku = None
        if img_val:
            if img_val.startswith("http"):
                import requests, os
                try:
                    resp = requests.get(img_val, timeout=5)
                    resp.raise_for_status()
                    target_sku = f"CS-{os.urandom(2).hex().upper()}"
                    thumb_path = os.path.join('static', 'scraped_thumbnails', f"{target_sku}.png")
                    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                    with open(thumb_path, 'wb') as f:
                        f.write(resp.content)
                    local_img_path = thumb_path
                except Exception as e:
                    print(f"Failed to download manual image: {e}")
                    local_img_path = img_val
            else:
                local_img_path = img_val
        return local_img_path, target_sku

    def send_to_staging(self):
        name = self.name_ent.get().strip()
        set_name = self.set_ent.get().strip()
        seq = self.seq_ent.get().strip()
        price_str = self.price_ent.get().strip()
        game_val = getattr(self, 'game_var', ctk.StringVar(value='Pokemon')).get()
        
        if not name or not set_name or not price_str:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Name, Set Name, and Price are required.")
            return
            
        import os, difflib
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_paths = {
            "English": os.path.join(base_dir, 'set_names.txt'),
            "Japanese": os.path.join(base_dir, 'set_names_ja.txt'),
            "Chinese": os.path.join(base_dir, 'set_names_zh.txt')
        }
        
        all_sets = []
        for path in file_paths.values():
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    all_sets.extend([line.strip() for line in f if line.strip()])
                    
        existing_set = False
        for s in all_sets:
            if s.lower() == set_name.lower():
                existing_set = True
                break
                
        if not existing_set:
            matches = difflib.get_close_matches(set_name, all_sets, n=1, cutoff=0.6)
            dialog = SetValidationDialog(self, set_name, matches[0] if matches else None)
            self.wait_window(dialog)
            
            if dialog.result == "cancel":
                return
            elif dialog.result == "use_match":
                set_name = dialog.selected_set_name
            elif dialog.result == "new_set":
                set_name = dialog.selected_set_name
                target_file = file_paths.get(dialog.selected_language, file_paths["English"])
                with open(target_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{set_name}")
                


        try:
            price = float(price_str)
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Error", "Price must be a valid number.")
            return
            
        img_val = self.img_ent.get().strip()
        local_img_path, target_sku = self._process_image_download(img_val)
        
        data = {
            'name': name,
            'set_name': set_name,
            'sequence_number': seq,
            'variant': self.var_var.get(),
            'condition': self.cond_var.get(),
            'card_type': 'Card',
            'market_price': price,
            'quantity': 1,
            'image_path': local_img_path,
            'confidence_scores': {'market_price': 100, 'name': 100, 'set_name': 100}
        }
        
        # Inject grade if toggled
        if self.is_graded_var.get():
            grade_str = f"{self.grade_company_var.get()} {self.grade_val_var.get()}"
            data['grade'] = grade_str
            data['condition'] = grade_str
        if target_sku:
            data['sku'] = target_sku
            
        if hasattr(self, 'add_callback') and self.add_callback:
            self.add_callback(data)
        else:
            from logic import add_item_to_staging
            add_item_to_staging(data, refresh_callback=self.refresh_callback)
        
        self.name_ent.delete(0, 'end')
        self.set_ent.delete(0, 'end')
        self.seq_ent.delete(0, 'end')
        self.price_ent.delete(0, 'end')
        self.img_ent.delete(0, 'end')
        self.cond_var.set("Near Mint")
        self.var_var.set("Normal")
        self.is_graded_var.set(False)
        self._toggle_graded_options()
        self.img_preview_lbl.configure(image="", text="[ No Image ]")
        
        from tkinter import messagebox
        messagebox.showinfo("Success", "Sent to Staging Dock!")

    def send_sealed_to_staging(self):
        name = self.sealed_name_ent.get().strip()
        set_name = self.sealed_set_ent.get().strip()
        price_str = self.sealed_price_ent.get().strip()
        img_val = self.sealed_img_ent.get().strip()
        
        if not name or not set_name or not price_str:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Product Name, Set Name, and Price are required.")
            return
            
        import os, difflib
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_paths = {
            "English": os.path.join(base_dir, 'set_names.txt'),
            "Japanese": os.path.join(base_dir, 'set_names_ja.txt'),
            "Chinese": os.path.join(base_dir, 'set_names_zh.txt')
        }
        
        all_sets = []
        for path in file_paths.values():
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    all_sets.extend([line.strip() for line in f if line.strip()])
                    
        existing_set = False
        for s in all_sets:
            if s.lower() == set_name.lower():
                existing_set = True
                break
                
        if not existing_set:
            matches = difflib.get_close_matches(set_name, all_sets, n=1, cutoff=0.6)
            dialog = SetValidationDialog(self, set_name, matches[0] if matches else None)
            self.wait_window(dialog)
            
            if dialog.result == "cancel":
                return
            elif dialog.result == "use_match":
                set_name = dialog.selected_set_name
            elif dialog.result == "new_set":
                set_name = dialog.selected_set_name
                target_file = file_paths.get(dialog.selected_language, file_paths["English"])
                with open(target_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{set_name}")
                
        try:
            price = float(price_str)
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Error", "Price must be a valid number.")
            return
            
        local_img_path, target_sku = self._process_image_download(img_val)
        
        data = {
            'name': name,
            'set_name': set_name,
            'sequence_number': '',
            'variant': 'Normal',
            'condition': 'Near Mint',
            'card_type': 'Sealed',
            'is_sealed': True,
            'market_price': price,
            'quantity': 1,
            'image_path': local_img_path,
            'confidence_scores': {'market_price': 100, 'name': 100, 'set_name': 100}
        }
        
        if target_sku:
            data['sku'] = target_sku
        
        from logic import add_item_to_staging
        add_item_to_staging(data, refresh_callback=self.refresh_callback)
        
        self.sealed_name_ent.delete(0, 'end')
        self.sealed_set_ent.delete(0, 'end')
        self.sealed_price_ent.delete(0, 'end')
        self.sealed_img_ent.delete(0, 'end')
        self.refresh_image_preview("", self.sealed_img_preview_lbl)
        
        from tkinter import messagebox
        messagebox.showinfo("Success", "Sealed Product Sent to Staging!")

class ShopifySyncFrame(ctk.CTkFrame):
    def __init__(self, master, refresh_callback=None):
        super().__init__(master, fg_color="transparent")
        self.refresh_callback = refresh_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Shopify Sync Overview", font=ctk.CTkFont(size=24, weight="bold"), text_color="#6366F1").pack(side="left")
        ctk.CTkButton(header, text="🔄 Refresh Sync Queue", fg_color="#2fa572", command=self.refresh_list).pack(side="right", padx=5)
        self.sync_btn = ctk.CTkButton(header, text="🚀 Force Sync", command=self.run_force_sync, fg_color="#8B5CF6", hover_color="#7C3AED", font=ctk.CTkFont(weight="bold"))
        self.sync_btn.pack(side="right", padx=5)
        
        # Progress Frame (initially hidden)
        self.progress_frame = ctk.CTkFrame(self, fg_color="#18181B", border_width=1, border_color="#374151", corner_radius=8)
        self.progress_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.progress_frame.grid_columnconfigure(1, weight=1)
        self.progress_frame.grid_remove()

        self.progress_lbl = ctk.CTkLabel(self.progress_frame, text="Sync Progress: 0 / 0 (0 left)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10B981")
        self.progress_lbl.grid(row=0, column=0, padx=15, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color="#10B981", fg_color="#27272A", height=12)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(10, 15), pady=10)
        self.progress_bar.set(0)
        
        # Main Layout
        self.scroll = ctk.CTkScrollableFrame(self, label_text="Pending Updates & Recent Syncs")
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        # Button Frame for Bottom Actions
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=(0, 20))

        # Clear Completed Button
        self.clear_btn = ctk.CTkButton(btn_frame, text="🧹 Clear Completed", fg_color="#944747", hover_color="#7A3B3B", command=self.clear_completed)
        self.clear_btn.pack(side="left", padx=10)
        
        # Clear Pending Button
        self.clear_pending_btn = ctk.CTkButton(btn_frame, text="🗑️ Clear Pending", fg_color="#D97706", hover_color="#B45309", command=self.clear_pending)
        self.clear_pending_btn.pack(side="left", padx=10)
        
        # Verify Prices Button
        self.verify_btn = ctk.CTkButton(btn_frame, text="🔍 Verify & Fix Shopify Prices", fg_color="#6366F1", hover_color="#4F46E5", command=self.verify_shopify_prices)
        self.verify_btn.pack(side="left", padx=10)
        
        self.refresh_list()

    def run_force_sync(self):
        try:
            inv_frame = self.master.master.frames.get("inv")
            if inv_frame:
                inv_frame.run_force_sync()
        except Exception as e:
            print(f"Error triggering force sync from Shopify frame: {e}")

    def verify_shopify_prices(self):
        from tkinter import messagebox
        import threading
        
        if not messagebox.askyesno("Verify Shopify", "This will scan your entire Shopify catalog and compare it to the local DB. Any mismatched prices or stock will be added to the Outbox to be fixed. This may take a few moments. Proceed?"):
            return
            
        self.verify_btn.configure(state="disabled", text="Scanning...")
        
        def run_verify():
            from core import CoreManager
            core = CoreManager(None, None, None, start_poller=False)
            success, msg = core.verify_shopify_consistency()
            
            def on_complete():
                self.verify_btn.configure(state="normal", text="🔍 Verify & Fix Shopify Prices")
                if success:
                    messagebox.showinfo("Verification Complete", msg)
                    self.refresh_list()
                else:
                    messagebox.showerror("Verification Failed", msg)
            
            self.after(0, on_complete)
            
        threading.Thread(target=run_verify, daemon=True).start()

    def clear_pending(self):
        from tkinter import messagebox
        from database import db_session, SyncOutbox
        if messagebox.askyesno("Confirm Action", "Are you sure you want to delete ALL pending syncs? This is useful if a card was deleted on Shopify, but doing this means you will have to manually sync any pending changes. Proceed?"):
            try:
                db_session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'pending').delete(synchronize_session=False)
                db_session.commit()
                self.refresh_list()
            except Exception as e:
                db_session.rollback()
                messagebox.showerror("Error", f"Failed to clear pending syncs: {e}")

    def clear_completed(self):
        from database import db_session, SyncOutbox
        try:
            db_session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'synced').delete(synchronize_session=False)
            db_session.commit()
            self.refresh_list()
        except Exception as e:
            db_session.rollback()
            print(f"Error clearing completed syncs: {e}")

    def refresh_list(self):
        for child in self.scroll.winfo_children():
            child.destroy()
            
        from database import db_session, SyncOutbox
        outbox_items = db_session.query(SyncOutbox).order_by(SyncOutbox.timestamp.desc()).limit(100).all()
        
        if not outbox_items:
            ctk.CTkLabel(self.scroll, text="No items pending sync or recently synced.", font=ctk.CTkFont(size=16), text_color="#8E8E8E").pack(pady=40)
            return
            
        for item in outbox_items:
            row = ctk.CTkFrame(self.scroll, fg_color="#18181B", border_width=1, border_color="#27272A", corner_radius=8)
            row.pack(fill="x", padx=10, pady=5)
            
            time_str = item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ctk.CTkLabel(row, text=f"[{time_str}]", font=ctk.CTkFont(family="Courier", size=14), text_color="#8E8E8E").pack(side="left", padx=10, pady=15)
            
            action_color = "#3b8ed0" if item.action_type.lower() == 'import' else "#f39c12"
            
            row_color = "#22C55E" if item.sync_status == 'synced' else "#EAB308"
            
            ctk.CTkLabel(row, text=item.action_type.upper(), font=ctk.CTkFont(weight="bold"), text_color=row_color, width=80).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"SKU: {item.sku}", font=ctk.CTkFont(size=14, weight="bold"), text_color=row_color).pack(side="left", padx=10)
            
            if item.quantity_change:
                qty_txt = f"+{item.quantity_change}" if item.quantity_change > 0 else str(item.quantity_change)
                ctk.CTkLabel(row, text=f"Qty: {qty_txt}", font=ctk.CTkFont(weight="bold"), text_color=row_color).pack(side="left", padx=20)
                
            status_text = "✅ SYNCED" if item.sync_status == 'synced' else "⏳ PENDING"
            ctk.CTkLabel(row, text=status_text, font=ctk.CTkFont(weight="bold"), text_color=row_color).pack(side="right", padx=20)



class CardsToRemoveFrame(ctk.CTkFrame):
    """Display-only list of sold cards that still appear in the Collectr export.
    Items are visual markers only — nothing is written to the database.
    The panel is shown/hidden by CardShopApp based on recon results.
    """
    def __init__(self, master, on_empty_callback):
        super().__init__(master, fg_color="transparent")
        self.on_empty_callback = on_empty_callback  # called when all items confirmed
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="🗑 CARDS TO REMOVE FROM COLLECTR",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#EF4444"
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="These cards were sold through the program but still appear in your Collectr portfolio.\n"
                 "Confirm each one after removing it from Collectr.",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            justify="left"
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.mark_all_btn = ctk.CTkButton(
            header,
            text="✅ Mark All Removed",
            fg_color="#16A34A",
            hover_color="#15803D",
            font=ctk.CTkFont(weight="bold"),
            width=180,
            command=self.confirm_all
        )
        self.mark_all_btn.grid(row=0, column=1, rowspan=2, padx=(20, 0), sticky="e")

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        self.scroll.grid_columnconfigure(0, weight=1)

        # Internal state: list of (set_name, card_dict) tuples
        self._items = []  # [(set_name, {name, num, sku}), ...]
        self._row_widgets = {}  # key=(set_name, sku) -> frame widget

    def load_removal_list(self, removal_list: dict):
        """Populate the panel from a removal_list dict {set_name: [{name, num, sku}]}."""
        # Flatten and store
        self._items = []
        for set_name in sorted(removal_list.keys()):
            for card in removal_list[set_name]:
                self._items.append((set_name, card))
        self._rebuild_ui()

    def _rebuild_ui(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._row_widgets = {}

        if not self._items:
            ctk.CTkLabel(
                self.scroll,
                text="✅ All done! No cards left to remove from Collectr.",
                font=ctk.CTkFont(size=16),
                text_color="#22C55E"
            ).pack(pady=60)
            return

        # Group by set for display
        from itertools import groupby
        current_set = None
        for set_name, card in self._items:
            if set_name != current_set:
                current_set = set_name
                # Set header label
                set_lbl = ctk.CTkLabel(
                    self.scroll,
                    text=f"  {set_name}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#6366F1",
                    anchor="w"
                )
                set_lbl.pack(fill="x", padx=10, pady=(12, 2))

            row_key = (set_name, card["sku"])
            row = ctk.CTkFrame(self.scroll, fg_color="#18181B", border_width=1, border_color="#27272A", corner_radius=8)
            row.pack(fill="x", padx=10, pady=3)
            row.grid_columnconfigure(2, weight=1)

            img_lbl = ctk.CTkLabel(row, text="Loading...", width=60, height=84)
            img_lbl.grid(row=0, column=0, padx=6, pady=6)
            self._load_removal_image(card["sku"], img_lbl)

            ctk.CTkLabel(
                row,
                text=f"#{card['num']}",
                font=ctk.CTkFont(family="Courier", size=12),
                text_color="#6B7280",
                width=60
            ).grid(row=0, column=1, padx=(12, 6), pady=12)

            ctk.CTkLabel(
                row,
                text=card["name"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            ).grid(row=0, column=2, sticky="ew", padx=6, pady=12)

            ctk.CTkLabel(
                row,
                text=f"SKU: {card['sku']}",
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
                width=110
            ).grid(row=0, column=3, padx=10, pady=12)

            confirm_btn = ctk.CTkButton(
                row,
                text="✅ Confirmed Removed",
                fg_color="#1D4ED8",
                hover_color="#1E40AF",
                width=160,
                command=lambda k=row_key: self._confirm_item(k)
            )
            confirm_btn.grid(row=0, column=4, padx=12, pady=8)

            readd_btn = ctk.CTkButton(
                row,
                text="➕ Readd to collection",
                fg_color="#2fa572",
                hover_color="#268a5f",
                width=160,
                command=lambda k=row_key, c=card, s=set_name: self._readd_item(k, c, s)
            )
            readd_btn.grid(row=0, column=5, padx=(0, 12), pady=8)

            self._row_widgets[row_key] = row

    def _confirm_item(self, key):
        """Dismiss a single card from the removal list and mark its sales as reconciled."""
        from database import db_session, Sale
        for s, c in self._items:
            if (s, c["sku"]) == key:
                skus = c.get("skus", [c["sku"]])
                qty = c.get("qty_to_remove", 1)
                sales = db_session.query(Sale).filter(Sale.sku.in_(skus), Sale.is_reconciled==False).order_by(Sale.timestamp.asc()).limit(qty).all()
                for sale in sales:
                    sale.is_reconciled = True
                db_session.commit()
                break
                
        self._items = [(s, c) for s, c in self._items if (s, c["sku"]) != key]
        self._rebuild_ui()
        if not self._items:
            self.on_empty_callback()

    def _load_removal_image(self, sku, lbl):
        import threading
        def fetch():
            try:
                from database import db_session, InventoryItem
                import urllib.request
                from PIL import Image
                from io import BytesIO
                
                inv_item = db_session.query(InventoryItem).filter_by(sku=sku).first()
                if inv_item and inv_item.image_url:
                    req = urllib.request.Request(inv_item.image_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        img_data = response.read()
                        image = Image.open(BytesIO(img_data))
                        image = image.resize((60, 84))
                        photo = ctk.CTkImage(light_image=image, dark_image=image, size=(60, 84))
                        lbl.after(0, lambda: lbl.configure(image=photo, text=""))
                else:
                    lbl.after(0, lambda: lbl.configure(text="No Img"))
            except Exception as e:
                lbl.after(0, lambda: lbl.configure(text="Error"))
                print(f"Error loading image for removal {sku}: {e}")
        threading.Thread(target=fetch, daemon=True).start()

    def _readd_item(self, key, card, set_name):
        """Restore the card to the database (stock=1) and push to Shopify."""
        from database import db_session, InventoryItem, SyncOutbox, Sale
        from logic import calculate_shop_price
        sku = card['sku']
        inv_item = db_session.query(InventoryItem).filter_by(sku=sku).first()
        
        if inv_item:
            inv_item.stock = 1
            inv_item.sync_status = 'approved'
            calc_price = calculate_shop_price(inv_item.price) if not getattr(inv_item, 'shop_listing_price', None) else inv_item.shop_listing_price
        else:
            price = card.get('price', 1.0)
            inv_item = InventoryItem(
                sku=sku,
                name=card['name'],
                set_name=set_name,
                sequence_number=card['num'],
                cost=0.0,
                price=price,
                card_type='Card',
                condition='Near Mint',
                stock=1,
                sync_status='approved'
            )
            db_session.add(inv_item)
            calc_price = calculate_shop_price(price)

        db_session.query(Sale).filter_by(sku=sku).delete()

        outbox = SyncOutbox(action_type='stock_update', sku=sku, quantity_change=1, new_price=calc_price)
        db_session.add(outbox)
        db_session.commit()
        
        from tkinter import messagebox
        messagebox.showinfo("Restored", f"Successfully readded '{card['name']}' to collection and queued Shopify sync!")

        self._items = [(s, c) for s, c in self._items if (s, c["sku"]) != key]
        self._rebuild_ui()
        if not self._items:
            self.on_empty_callback()

    def confirm_all(self):
        """Dismiss all cards at once and mark all their sales as reconciled."""
        from database import db_session, Sale
        for s, c in self._items:
            skus = c.get("skus", [c["sku"]])
            qty = c.get("qty_to_remove", 1)
            sales = db_session.query(Sale).filter(Sale.sku.in_(skus), Sale.is_reconciled==False).order_by(Sale.timestamp.asc()).limit(qty).all()
            for sale in sales:
                sale.is_reconciled = True
        db_session.commit()
        
        self._items = []
        self._rebuild_ui()
        self.on_empty_callback()

class CardsToAddFrame(ctk.CTkFrame):
    def __init__(self, master, on_empty_callback):
        super().__init__(master, fg_color="transparent")
        self.on_empty_callback = on_empty_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="➕ CARDS TO ADD TO COLLECTR",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#3B82F6"
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="These cards are in your local DB but missing from your Collectr portfolio.\n"
                 "Confirm each one after adding it to Collectr.",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            justify="left"
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.mark_all_btn = ctk.CTkButton(
            header,
            text="✅ Mark All Added",
            fg_color="#16A34A",
            hover_color="#15803D",
            font=ctk.CTkFont(weight="bold"),
            width=180,
            command=self.confirm_all
        )
        self.mark_all_btn.grid(row=0, column=1, rowspan=2, padx=(20, 0), sticky="e")

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._items = []  # [(set_name, {name, num, sku}), ...]
        self._row_widgets = {}

    def load_add_list(self, add_list: dict):
        """Populate the panel from a missing_from_collectr dict {set_name: [{name, num, sku}]}."""
        self._items = []
        for set_name in sorted(add_list.keys()):
            for card in add_list[set_name]:
                self._items.append((set_name, card))
        self._rebuild_ui()

    def _rebuild_ui(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._row_widgets = {}

        if not self._items:
            ctk.CTkLabel(
                self.scroll,
                text="✅ All done! No cards left to add to Collectr.",
                font=ctk.CTkFont(size=16),
                text_color="#22C55E"
            ).pack(pady=60)
            return

        current_set = None
        for set_name, card in self._items:
            if set_name != current_set:
                current_set = set_name
                # Set header label
                set_lbl = ctk.CTkLabel(
                    self.scroll,
                    text=f"  {set_name}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#6366F1",
                    anchor="w"
                )
                set_lbl.pack(fill="x", padx=10, pady=(12, 2))

            row_key = (set_name, card["sku"])
            row = ctk.CTkFrame(self.scroll, fg_color="#18181B", border_width=1, border_color="#27272A", corner_radius=8)
            row.pack(fill="x", padx=10, pady=3)
            row.grid_columnconfigure(2, weight=1)

            # Image
            import os
            from PIL import Image
            thumb_path = os.path.join('static', 'scraped_thumbnails', f"{card['sku']}.png")
            if os.path.exists(thumb_path):
                try:
                    img = Image.open(thumb_path)
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 56))
                    img_lbl = ctk.CTkLabel(row, image=ctk_img, text="")
                    img_lbl.image = ctk_img
                except Exception:
                    img_lbl = ctk.CTkLabel(row, text="[No Image]", font=ctk.CTkFont(size=10), width=40, height=56)
            else:
                img_lbl = ctk.CTkLabel(row, text="[No Image]", font=ctk.CTkFont(size=10), width=40, height=56)
            img_lbl.grid(row=0, column=0, padx=(12, 6), pady=8)

            ctk.CTkLabel(
                row,
                text=f"#{card['num']}",
                font=ctk.CTkFont(family="Courier", size=12),
                text_color="#6B7280",
                width=60
            ).grid(row=0, column=1, padx=(6, 6), pady=12)

            ctk.CTkLabel(
                row,
                text=card["name"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            ).grid(row=0, column=2, sticky="ew", padx=6, pady=12)

            missing_qty = card.get("missing_qty", 1)
            ctk.CTkLabel(
                row,
                text=f"SKU: {card['sku']} (Qty: {missing_qty})",
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
                width=140
            ).grid(row=0, column=3, padx=10, pady=12)

            confirm_btn = ctk.CTkButton(
                row,
                text="✅ Added to Collectr",
                fg_color="#3B82F6",
                hover_color="#2563EB",
                width=150,
                command=lambda k=row_key: self._confirm_item(k)
            )
            confirm_btn.grid(row=0, column=4, padx=6, pady=8)

            remove_btn = ctk.CTkButton(
                row,
                text="✕ Remove from Inventory",
                fg_color="#DC2626",
                hover_color="#991B1B",
                width=150,
                command=lambda k=row_key, c=card: self._remove_item_from_inventory(k, c)
            )
            remove_btn.grid(row=0, column=5, padx=(6, 12), pady=8)

            self._row_widgets[row_key] = row

    def _confirm_item(self, key):
        self._items = [(s, c) for s, c in self._items if (s, c["sku"]) != key]
        self._rebuild_ui()
        if not self._items:
            self.on_empty_callback()

    def _remove_item_from_inventory(self, key, card):
        from database import db_session, InventoryItem, SyncOutbox
        from logic import calculate_shop_price
        from tkinter import messagebox

        sku = card['sku']
        missing_qty = card.get('missing_qty', 1)
        inv_item = db_session.query(InventoryItem).filter_by(sku=sku).first()
        
        if inv_item:
            inv_item.stock = max(0, inv_item.stock - missing_qty)
            inv_item.needs_update = True
            calc_price = calculate_shop_price(inv_item.price) if not getattr(inv_item, 'shop_listing_price', None) else inv_item.shop_listing_price
            
            outbox = SyncOutbox(action_type='stock_update', sku=sku, quantity_change=-missing_qty, new_price=calc_price)
            db_session.add(outbox)
            db_session.commit()
            
            messagebox.showinfo("Removed", f"Successfully removed {missing_qty} of '{card['name']}' from local inventory and queued Shopify stock deduction!")
        
        self._items = [(s, c) for s, c in self._items if (s, c["sku"]) != key]
        self._rebuild_ui()
        if not self._items:
            self.on_empty_callback()

    def confirm_all(self):
        self._items = []
        self._rebuild_ui()
        self.on_empty_callback()

class ExportSelectedModal(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Select Cards to Export")
        self.geometry("750x550")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.transient(master)
        self.grab_set()
        
        # State
        self.checkboxes = {}
        self.items_data = []
        self.checkbox_vars = []
        self.limit = 50
        self.offset = 0
        self.shift_pressed = False
        self.last_clicked_idx = None
        
        def on_shift_press(e):
            self.shift_pressed = True
        def on_shift_release(e):
            self.shift_pressed = False
            
        self.bind("<KeyPress-Shift_L>", on_shift_press)
        self.bind("<KeyRelease-Shift_L>", on_shift_release)
        self.bind("<KeyPress-Shift_R>", on_shift_press)
        self.bind("<KeyRelease-Shift_R>", on_shift_release)
        
        # Header
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(header_f, text="Select Cards for Excel Export", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        btn_f = ctk.CTkFrame(header_f, fg_color="transparent")
        btn_f.pack(side="right")
        
        ctk.CTkButton(btn_f, text="Select All", width=100, command=self.select_all).pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="Deselect All", width=100, command=self.deselect_all).pack(side="left", padx=5)
        
        # Scrollable Frame
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        self.scroll.bind("<KeyPress-Shift_L>", on_shift_press)
        self.scroll.bind("<KeyRelease-Shift_L>", on_shift_release)
        self.scroll.bind("<KeyPress-Shift_R>", on_shift_press)
        self.scroll.bind("<KeyRelease-Shift_R>", on_shift_release)
        
        self.load_more_btn = ctk.CTkButton(self.scroll, text="Load More", command=self.load_items, fg_color="#3b8ed0")
        
        # Bottom controls
        bottom_f = ctk.CTkFrame(self, fg_color="transparent")
        bottom_f.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        self.status_lbl = ctk.CTkLabel(bottom_f, text="")
        self.status_lbl.pack(side="left")
        
        self.export_btn = ctk.CTkButton(bottom_f, text="Generate Export", fg_color="#F59E0B", hover_color="#D97706", command=self.generate_export)
        self.export_btn.pack(side="right")
        
        self.load_items()
        
    def load_items(self):
        from database import db_session, InventoryItem
        
        new_items = db_session.query(InventoryItem).filter(InventoryItem.stock > 0).order_by(InventoryItem.date_added.desc()).offset(self.offset).limit(self.limit).all()
        
        if self.load_more_btn.winfo_ismapped() or self.load_more_btn.winfo_manager():
            self.load_more_btn.pack_forget()
            
        for item in new_items:
            date_str = item.date_added.strftime('%Y-%m-%d %H:%M') if item.date_added else "Unknown"
            text = f"[{date_str}] {item.name} - {item.set_name} #{item.sequence_number} (SKU: {item.sku})"
            var = ctk.BooleanVar(value=False)
            
            idx = len(self.checkbox_vars)
            self.checkbox_vars.append(var)
            
            row_f = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row_f.pack(fill="x", pady=2)
            
            chk = ctk.CTkCheckBox(row_f, text=text, variable=var, command=lambda i=idx: self.on_checkbox_toggle(i))
            chk.pack(anchor="w", padx=5)
            self.checkboxes[item.sku] = (item, var)
            self.items_data.append(item)
            
        self.offset += len(new_items)
        
        if len(new_items) == self.limit:
            self.load_more_btn.pack(pady=10)
            
    def on_checkbox_toggle(self, idx):
        if self.shift_pressed and self.last_clicked_idx is not None:
            start = min(self.last_clicked_idx, idx)
            end = max(self.last_clicked_idx, idx)
            target = self.checkbox_vars[idx].get()
            for i in range(start, end + 1):
                self.checkbox_vars[i].set(target)
        self.last_clicked_idx = idx
            
    def select_all(self):
        for item, var in self.checkboxes.values():
            var.set(True)
            
    def deselect_all(self):
        for item, var in self.checkboxes.values():
            var.set(False)
            
    def generate_export(self):
        selected_items = [item for item, var in self.checkboxes.values() if var.get()]
        if not selected_items:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select at least one card to export.", parent=self)
            return
            
        import threading
        def _export():
            try:
                from openpyxl import Workbook
                from openpyxl.drawing.image import Image as OpenpyxlImage
                import qrcode
                import os
                import tempfile
                from tkinter import messagebox
                
                self.after(0, lambda: self.export_btn.configure(state="disabled", text="⏳ Exporting..."))
                
                wb = Workbook()
                ws = wb.active
                ws.title = "Selected Inventory"
                
                ws.append(["Name", "Set Name", "Set Number", "SKU", "QR Code"])
                ws.column_dimensions['A'].width = 40
                ws.column_dimensions['B'].width = 30
                ws.column_dimensions['C'].width = 15
                ws.column_dimensions['D'].width = 25
                ws.column_dimensions['E'].width = 15
                
                temp_dir = tempfile.mkdtemp()
                
                for i, item in enumerate(selected_items, start=2):
                    ws.row_dimensions[i].height = 75
                    ws.cell(row=i, column=1, value=item.name)
                    ws.cell(row=i, column=2, value=item.set_name)
                    ws.cell(row=i, column=3, value=item.sequence_number)
                    ws.cell(row=i, column=4, value=item.sku)
                    
                    qr = qrcode.make(item.sku)
                    qr = qr.resize((100, 100))
                    temp_path = os.path.join(temp_dir, f"{item.sku}.png")
                    qr.save(temp_path)
                    
                    img = OpenpyxlImage(temp_path)
                    ws.add_image(img, f"E{i}")
                
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                export_path = os.path.join(downloads_path, "Selected_Inventory_Export.xlsx")
                
                counter = 1
                while os.path.exists(export_path):
                    export_path = os.path.join(downloads_path, f"Selected_Inventory_Export_{counter}.xlsx")
                    counter += 1
                    
                wb.save(export_path)
                
                self.after(0, lambda path=export_path: messagebox.showinfo("Export Successful", f"Selected inventory exported to:\n{path}", parent=self))
                self.after(0, self.destroy)
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("Export Failed", f"An error occurred: {e}", parent=self))
            finally:
                try:
                    self.after(0, lambda: self.export_btn.configure(state="normal", text="Generate Export"))
                except: pass
                
        threading.Thread(target=_export, daemon=True).start()

class CardShopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Apply Theme
        import os
        theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odin_theme.json")
        if os.path.exists(theme_path):
            ctk.set_default_color_theme(theme_path)
        ctk.set_appearance_mode("dark")

        # Aesthetics
        self.configure(fg_color="#0A0A0A")
        self.title("Mimir's Vault")
        self.geometry("1600x900")
        self.minsize(1280, 720)
        self.after(0, lambda: self.state('zoomed'))
        
        # Startup DB setup
        try:
            init_db()
            migrate()
            for folder in [os.path.join('static', 'scraped_thumbnails'), os.path.join('static', 'barcodes'), os.path.join('static', 'config')]:
                os.makedirs(folder, exist_ok=True)
            start_background_worker(core_manager)
            self.sync_missing_images_in_background()
            
            # Start Gmail Monitor
            get_gmail_monitor(self._gmail_monitor_callback).start()
        except Exception as e:
            print(f"[!] Startup Critical Error: {e}")
            messagebox.showerror("Startup Error", str(e))
            self.destroy()
            return

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def sync_missing_images_in_background(self):
        def _dl():
            import requests, os, time
            from database import db_session, InventoryItem, StagingItem
            
            try:
                # Sync Inventory Items
                inv_items = db_session.query(InventoryItem).filter((InventoryItem.image_url.like('http%')) | (InventoryItem.custom_image_url.like('http%'))).all()
                for i in inv_items:
                    url = i.custom_image_url if (i.custom_image_url and i.custom_image_url.startswith('http')) else i.image_url
                    if not url or not url.startswith('http'):
                        continue
                    thumb_path = os.path.join('static', 'scraped_thumbnails', f"{i.sku}.png")
                    if not os.path.exists(thumb_path):
                        try:
                            r = requests.get(url, timeout=5)
                            if r.status_code == 200:
                                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                                with open(thumb_path, 'wb') as f:
                                    f.write(r.content)
                            time.sleep(0.2)
                        except: pass
            except: pass

            try:
                # Sync Staging Items
                staging_items = db_session.query(StagingItem).filter(StagingItem.image_path.like('http%')).all()
                for i in staging_items:
                    if not i.image_path or not i.image_path.startswith('http'):
                        continue
                    thumb_path = os.path.join('static', 'scraped_thumbnails', f"{i.sku}.png")
                    if not os.path.exists(thumb_path):
                        try:
                            r = requests.get(i.image_path, timeout=5)
                            if r.status_code == 200:
                                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                                with open(thumb_path, 'wb') as f:
                                    f.write(r.content)
                            time.sleep(0.2)
                        except: pass
            except: pass

        import threading
        threading.Thread(target=_dl, daemon=True).start()
        
        # Main window layout:
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main content
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar Frame
        self.sidebar_frame = ctk.CTkFrame(self, width=250, fg_color="#121214", corner_radius=0, border_width=1, border_color="#1F1F23")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.pack_propagate(False)

        # App Title/Logo
        self.title_lbl = ctk.CTkLabel(self.sidebar_frame, text="MIMIR'S VAULT", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color="#FFFFFF")
        self.title_lbl.pack(pady=25)

        self.simulate_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🛒 Simulate Shopify Purchase",
            height=32,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Segoe UI", 12, "bold"),
            command=self.simulate_shopify_purchase
        )

        # Nav Buttons Panel (Vertical)
        nav_panel = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        nav_panel.pack(fill="x", padx=15, pady=10)

        self.nav_btns = {}
        screens = [
            ("Dashboard", "dash"),
            ("Intake Studio", "studio"),
            ("Inventory", "inv"),
            ("Live POS", "live_pos"),
            ("History", "history"),
            ("Sold Online", "sold_online"),
            ("Review Staging", "review"),
            ("Shopify Sync", "shopify"),
            ("Settings", "sync")
        ]

        for text, key in screens:
            btn = ctk.CTkButton(
                nav_panel,
                text=text,
                width=220,
                height=40,
                fg_color="transparent",
                text_color="#8E8E8E",
                hover_color="#242424",
                font=("Segoe UI", 12, "bold"),
                command=lambda k=key: self.select_screen(k)
            )
            btn.pack(fill="x", pady=5)
            self.nav_btns[key] = btn

        # "Cards to Remove" nav button — hidden until recon finds items
        self.remove_nav_btn = ctk.CTkButton(
            nav_panel,
            text="🗑 Cards to Remove",
            width=220,
            height=40,
            fg_color="#7F1D1D",
            text_color="#FCA5A5",
            hover_color="#991B1B",
            font=("Segoe UI", 12, "bold"),
            command=lambda: self.select_screen("remove")
        )
        # Start hidden — shown only when there are cards to remove
        self.nav_btns["remove"] = self.remove_nav_btn

        # "Cards to Add" nav button
        self.add_nav_btn = ctk.CTkButton(
            nav_panel,
            text="➕ Cards to Add",
            width=220,
            height=40,
            fg_color="#1E3A8A",
            text_color="#93C5FD",
            hover_color="#1E40AF",
            font=("Segoe UI", 12, "bold"),
            command=lambda: self.select_screen("add")
        )
        self.nav_btns["add"] = self.add_nav_btn

        # Web Checkout Server Launcher Panel
        web_panel = ctk.CTkFrame(self.sidebar_frame, fg_color="#18181B", corner_radius=8, border_width=1, border_color="#27272A")
        web_panel.pack(fill="x", padx=15, pady=20)
        
        web_title_f = ctk.CTkFrame(web_panel, fg_color="transparent")
        web_title_f.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(web_title_f, text="🌐 Web Checkout", font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF").pack(side="left")
        
        self.web_status_lbl = ctk.CTkLabel(web_title_f, text="● OFFLINE", font=ctk.CTkFont(size=12, weight="bold"), text_color="#EF4444")
        self.web_status_lbl.pack(side="right")
        
        self.web_launch_btn = ctk.CTkButton(
            web_panel,
            text="🚀 Launch Server",
            height=32,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=("Segoe UI", 12, "bold"),
            command=self.toggle_web_checkout
        )
        self.web_launch_btn.pack(fill="x", padx=10, pady=(5, 10))
        
        self.web_server_process = None

        # 2. Main Content Container
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # Global refresh bridge
        def refresh_all():
            if "dash" in self.frames and hasattr(self.frames["dash"], "refresh"):
                self.frames["dash"].refresh()
            for f in ["inv", "history", "updated", "review", "shopify"]:
                if f in self.frames and hasattr(self.frames[f], "refresh_list"):
                    self.frames[f].refresh_list()
            if "studio" in self.frames:
                self.frames["studio"].refresh_staging_dock()

        # Lazy Frame Definitions (instantiated on-demand to ensure instant startup)
        self.frame_definitions = {
            "studio": lambda: IntakeStudioFrame(self.main_container, refresh_all),
            "dash": lambda: MainDashboard(self.main_container),
            "inv": lambda: InventoryManagerFrame(self.main_container, refresh_all),
            "updated": lambda: UpdatedCardsFrame(self.main_container, refresh_all),
            "live_pos": lambda: LiveCheckoutFrame(self.main_container, refresh_all),
            "history": lambda: TradeHistoryFrame(self.main_container, refresh_all),
            "sold_online": lambda: SoldOnlineFrame(self.main_container, refresh_all),
            "review": lambda: ReviewSyncFrame(self.main_container, refresh_all),
            "shopify": lambda: ShopifySyncFrame(self.main_container, refresh_all),
            "sync": lambda: SettingsFrame(self.main_container, refresh_all),
            "remove": lambda: CardsToRemoveFrame(self.main_container, self.hide_remove_panel),
            "add": lambda: CardsToAddFrame(self.main_container, self.hide_add_panel),
        }
        self.frames = {}

        self.active_screen = None
        self.select_screen("dash")
        self.poll_output_queue()

    def toggle_sim_shopify_button(self, state):
        if state:
            self.simulate_btn.pack(after=self.title_lbl, pady=(0, 15), padx=15, fill="x")
        else:
            self.simulate_btn.pack_forget()

    def simulate_shopify_purchase(self):
        from database import db_session, InventoryItem, Sale, OnlinePullQueue
        from logic import output_queue
        import random
        
        try:
            inv_items = db_session.query(InventoryItem).filter(InventoryItem.stock > 0).all()
            if not inv_items:
                messagebox.showinfo("Simulate Purchase", "No in-stock inventory items found to simulate a purchase!")
                return
                
            inv_item = random.choice(inv_items)
            
            inv_item.stock -= 1
            
            price = inv_item.price if inv_item.price else 0.0
            cost = inv_item.cost if inv_item.cost else 0.0
            profit = price - cost
            sale = Sale(
                item_name=inv_item.name,
                sku=inv_item.sku,
                sold_price=price,
                profit=profit,
                transaction_type="Online Sale"
            )
            db_session.add(sale)
            
            order_id = f"SIM-{random.randint(1000, 9999)}"
            pull_req = OnlinePullQueue(
                order_id=order_id,
                sku=inv_item.sku,
                status='pending_pull'
            )
            db_session.add(pull_req)
            db_session.commit()
            
            output_queue.put({
                'type': 'online_sale',
                'card_name': inv_item.name,
                'set_name': inv_item.set_name,
                'sequence_number': inv_item.sequence_number,
                'condition': inv_item.condition,
                'order_id': order_id
            })
            
            print(f"[*] Simulated Shopify purchase for {inv_item.name} (Order {order_id})")
        except Exception as e:
            print(f"[!] Error simulating Shopify purchase: {e}")
            messagebox.showerror("Simulation Error", f"Failed to simulate purchase: {e}")

    def poll_output_queue(self):
        """Polls the output queue for processed card data and updates the UI."""
        from logic import output_queue
        import queue
        processed_any = False
        try:
            while True:
                card_data = output_queue.get_nowait()
                processed_any = True
                
                # Check for online sale notification
                if isinstance(card_data, dict) and card_data.get('type') == 'online_sale':
                    NotificationToast(self, card_data)
                    # Refresh Sold Online tab if it's currently active
                    if "sold_online" in self.frames and hasattr(self.frames["sold_online"], "refresh_list"):
                        self.frames["sold_online"].refresh_list()
                    output_queue.task_done()
                    continue
                
                if isinstance(card_data, dict) and card_data.get('type') == 'refresh_sold_online':
                    if "sold_online" in self.frames and hasattr(self.frames["sold_online"], "refresh_list"):
                        self.frames["sold_online"].refresh_list()
                    output_queue.task_done()
                    continue
                
                if hasattr(self, 'active_overlay_view') and self.active_overlay_view and self.active_overlay_view.winfo_exists() and hasattr(self.active_overlay_view, 'on_card_added'):
                    self.active_overlay_view.on_card_added(card_data)
                elif "studio" in self.frames and hasattr(self.frames["studio"], "on_card_added"):
                    self.frames["studio"].on_card_added(card_data)
                    
                output_queue.task_done()
        except queue.Empty:
            pass

        self.after(100, self.poll_output_queue)

    def select_screen(self, key):
        if self.active_screen:
            active_btn = self.nav_btns.get(self.active_screen)
            if active_btn:
                if self.active_screen == "remove":
                    active_btn.configure(fg_color="#7F1D1D", text_color="#FCA5A5")
                else:
                    active_btn.configure(fg_color="transparent", text_color="#8E8E8E")

        if key not in self.frames:
            self.frames[key] = self.frame_definitions[key]()
            self.frames[key].grid(row=0, column=0, sticky="nsew")

        self.frames[key].tkraise()
        active_btn = self.nav_btns.get(key)
        if active_btn:
            active_btn.configure(fg_color="#6366F1", text_color="#FFFFFF")
        self.active_screen = key

    def show_remove_panel(self, removal_list: dict):
        """Populate the CardsToRemoveFrame with results and show the nav button."""
        if "remove" not in self.frames:
            self.frames["remove"] = self.frame_definitions["remove"]()
            self.frames["remove"].grid(row=0, column=0, sticky="nsew")
        self.frames["remove"].load_removal_list(removal_list)
        # Show the nav button if not already visible
        if not self.remove_nav_btn.winfo_ismapped():
            self.remove_nav_btn.pack(fill="x", pady=5)
        # Auto-navigate to the panel
        self.select_screen("remove")

    def hide_remove_panel(self):
        """Hide the Cards-to-Remove nav button and navigate back to Inventory."""
        if self.active_screen == "remove":
            self.select_screen("inv")
        self.remove_nav_btn.pack_forget()

    def show_add_panel(self, add_list: dict):
        """Populate the CardsToAddFrame with results and show the nav button."""
        if "add" not in self.frames:
            self.frames["add"] = self.frame_definitions["add"]()
            self.frames["add"].grid(row=0, column=0, sticky="nsew")
        self.frames["add"].load_add_list(add_list)
        if not self.add_nav_btn.winfo_ismapped():
            self.add_nav_btn.pack(fill="x", pady=5)

    def hide_add_panel(self):
        """Hide the Cards-to-Add nav button and navigate back to Inventory."""
        if self.active_screen == "add":
            self.select_screen("inv")
        self.add_nav_btn.pack_forget()

    def show_overlay(self, view_class, title="OVERLAY VIEW", **kwargs):
        overlay = OverlayLayer(self, title=title, on_close=kwargs.pop('on_close', None))
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        
        kwargs['close_callback'] = overlay.close
        view = view_class(overlay.content_container, **kwargs)
        view.grid(row=0, column=0, sticky="nsew")
        self.active_overlay_view = view
        return overlay


    def toggle_web_checkout(self):
        import subprocess
        import os
        import sys
        
        if self.web_server_process is None or self.web_server_process.poll() is not None:
            try:
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    
                python_exe = sys.executable
                venv_python = os.path.join(os.path.dirname(base_dir), ".venv", "Scripts", "python.exe")
                if not os.path.exists(venv_python):
                    venv_python = os.path.join(os.path.dirname(os.path.dirname(base_dir)), ".venv", "Scripts", "python.exe")
                if os.path.exists(venv_python):
                    python_exe = venv_python
                    
                script_path = os.path.join(base_dir, "web_checkout_module.py")
                self.web_server_process = subprocess.Popen([python_exe, script_path], cwd=base_dir)
                
                self.web_status_lbl.configure(text="● ONLINE", text_color="#22C55E")
                self.web_launch_btn.configure(text="🛑 Stop Server", fg_color="#DC2626", hover_color="#991B1B")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch web checkout server: {e}")
        else:
            try:
                self.web_server_process.terminate()
                self.web_server_process = None
                self.web_status_lbl.configure(text="● OFFLINE", text_color="#EF4444")
                self.web_launch_btn.configure(text="🚀 Launch Server", fg_color="#2563eb", hover_color="#1d4ed8")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop web checkout server: {e}")

    def on_closing(self):
        if self.web_server_process and self.web_server_process.poll() is None:
            try:
                self.web_server_process.terminate()
            except:
                pass
        get_gmail_monitor().stop()
        db_session.close()
        self.destroy()

    def _gmail_monitor_callback(self, status, msg_text):
        print(f"[UI] Gmail Monitor Update: {status} - {msg_text}")
        # In a real app we might update a status bar here.
        # But this is fine for basic logging.


if __name__ == "__main__":
    print(f"[*] LOCAL DATABASE TARGET: {DB_PATH}")
    app = CardShopApp()
    app.mainloop()
