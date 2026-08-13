from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import text
from datetime import datetime, timezone
import os

Base = declarative_base()

from config import ENVIRONMENT
import sys

# Get the directory where the script is running
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

if ENVIRONMENT == "TEST":
    DB_PATH = os.path.join(application_path, 'test_database.db')
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("[*] TEST ENVIRONMENT: Wiped existing test_database.db on launch.")
        except Exception as e:
            print(f"[!] Could not wipe test_database.db: {e}")
else:
    DB_PATH = os.path.join(application_path, 'card_shop.db')

env_path = os.path.join(application_path, '.env')

engine = create_engine(f'sqlite:///{DB_PATH}', connect_args={'check_same_thread': False, 'timeout': 30.0})

from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
print(f"[*] LOCAL DATABASE TARGET: {DB_PATH}")
print("[!] If you see 'no such column' errors, delete this file and restart the app.")

session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)
db_session = Session()

class InventoryItem(Base):
    __tablename__ = 'inventory_item'
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    set_name = Column(String(100))
    sequence_number = Column(String(50))
    cost = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    old_price = Column(Float, nullable=True)
    card_type = Column(String(50))
    variant = Column(String(50))
    condition = Column(String(50))
    stock = Column(Integer, default=0)
    last_sync = Column(DateTime, nullable=True)
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    needs_update = Column(Boolean, default=0)
    needs_review = Column(Boolean, default=False)
    image_url = Column(String(255), nullable=True)
    image_locked = Column(Boolean, default=False)
    sync_status = Column(String(50), default='paused')
    custom_image_url = Column(String(255), nullable=True)
    shop_listing_price = Column(Float, nullable=True)
    sticker_price = Column(Float, nullable=True)
    paused_stock = Column(Integer, default=0)
    game = Column(String(50), default='Pokemon')

class ReviewQueueItem(Base):
    __tablename__ = 'review_queue_item'
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    set_name = Column(String(100))
    sequence_number = Column(String(50))
    cost = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    old_price = Column(Float, nullable=True)
    card_type = Column(String(50))
    variant = Column(String(50))
    condition = Column(String(50))
    stock = Column(Integer, default=0)
    last_sync = Column(DateTime, nullable=True)
    date_added = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    needs_update = Column(Boolean, default=0)
    needs_review = Column(Boolean, default=False)
    image_url = Column(String(255), nullable=True)
    image_locked = Column(Boolean, default=False)
    sync_status = Column(String(50), default='paused')
    custom_image_url = Column(String(255), nullable=True)
    shop_listing_price = Column(Float, nullable=True)
    game = Column(String(50), default='Pokemon')

class PurchaseRecord(Base):
    __tablename__ = 'purchase_record'
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, default=1)
    cost_per_unit = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class Sale(Base):
    __tablename__ = 'sale'
    id = Column(Integer, primary_key=True)
    item_name = Column(String(100))
    sku = Column(String(50))
    sold_price = Column(Float)
    profit = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    transaction_type = Column(String(20))
    trade_in_value = Column(Float, default=0.0)
    processing_fees = Column(Float, default=0.0)
    trade_credit_deduction = Column(Float, default=0.0)
    net_revenue = Column(Float, default=0.0)
    game = Column(String(50), default='Pokemon')
    is_reconciled = Column(Boolean, default=False)

class OnlinePullQueue(Base):
    __tablename__ = 'online_pull_queue'
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), nullable=False)
    order_id = Column(String(100), nullable=True)
    status = Column(String(50), default='pending_pull')
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class SyncOutbox(Base):
    __tablename__ = 'sync_outbox'
    id = Column(Integer, primary_key=True)
    action_type = Column(String(50), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity_change = Column(Integer, nullable=False)
    new_price = Column(Float, nullable=True)
    sync_status = Column(String(50), default='pending')
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class StagingItem(Base):
    __tablename__ = 'staging_item'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    set_name = Column(String(100))
    sequence_number = Column(String(50))
    market_price = Column(Float, default=0.0)
    cost_basis = Column(Float, default=0.0)
    suggested_price = Column(Float, default=0.0)
    card_type = Column(String(50))
    variant = Column(String(50))
    condition = Column(String(50))
    quantity = Column(Integer, default=1)
    sku = Column(String(50), unique=True, nullable=False) # Format: 'CS-XXXX'
    image_path = Column(String(255))
    barcode_path = Column(String(255)) # Kept for backward compatibility
    needs_review = Column(Boolean, default=False)
    ocr_metadata = Column(String, default='{}') # Tracks confidence scores and vote history for consensus
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    image_locked = Column(Boolean, default=False)
    game = Column(String(50), default='Pokemon')

class PrintQueue(Base):
    __tablename__ = 'print_queue'
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), nullable=False)
    item_name = Column(String(100))
    is_printed = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class SystemSettings(Base):
    __tablename__ = 'system_settings'
    id = Column(Integer, primary_key=True)
    price_fluctuation_threshold = Column(Float, default=0.10)
    resticker_threshold = Column(Float, default=2.00)
    rounding_strategy = Column(String(50), default="Keep Raw TCG Decimal Payouts")
    paperweight_days = Column(Integer, default=60)
    buy_percentage = Column(Float, default=0.70)
    trade_percentage = Column(Float, default=0.80)
    ocr_x = Column(Integer, default=0)
    ocr_y = Column(Integer, default=0)
    ocr_width = Column(Integer, default=0)
    ocr_height = Column(Integer, default=0)
    sync_folder = Column(String(255), nullable=True) # Path to OneDrive/Dropbox folder
    sim_mode = Column(Boolean, default=False)
    markup_type = Column(String(50), default="Percentage (%)")
    markup_value = Column(Float, default=0.0)
    rounding_rule = Column(String(50), default="Exact/None")
    pokemon_icon_url = Column(String(255), default='')
    one_piece_icon_url = Column(String(255), default='')
    omit_graded_from_recon = Column(Boolean, default=False)
    graded_wizard_sales_count = Column(Integer, default=5)
    graded_wizard_omit_diff = Column(Float, default=20.0)
    gmail_monitor_enabled = Column(Boolean, default=False)
    gmail_address = Column(String(100), default='')
    gmail_app_password = Column(String(100), default='')
    gmail_folder = Column(String(100), default='INBOX')

class StoreSettings(Base):
    __tablename__ = 'store_settings'
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(255))

class ShippingRule(Base):
    __tablename__ = 'shipping_rule'
    id = Column(Integer, primary_key=True)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    additional_cost = Column(Float, nullable=False)
    card_type = Column(String(50), default="Card") # "Card" or "Sealed"

class PendingTrade(Base):
    """Persistent record of a placeholder trade agreed at a show or counter session."""
    __tablename__ = 'pending_trades'
    id = Column(Integer, primary_key=True)
    show_id = Column(String(100), nullable=True)          # Optional show/event label
    total_market_value = Column(Float, default=0.0)       # Market value of the trade-in lot
    total_cash_paid = Column(Float, default=0.0)          # Actual cash/credit paid out
    status = Column(String(50), default='pending')        # 'pending' | 'applied'
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class ShowPriceCapture(Base):
    __tablename__ = 'show_price_capture'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    item_count = Column(Integer, default=0)
    total_value = Column(Float, default=0.0)

class ShowPriceCaptureItem(Base):
    __tablename__ = 'show_price_capture_item'
    id = Column(Integer, primary_key=True)
    capture_id = Column(Integer, ForeignKey('show_price_capture.id'), nullable=False)
    sku = Column(String(50), nullable=False)
    sticker_price = Column(Float, nullable=False)

def init_db():
    Base.metadata.create_all(engine)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE sale ADD COLUMN is_reconciled BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        pass
        
    # Non-destructive performance indexes for high-frequency query columns
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_inventory_sku ON inventory_item (sku)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_inventory_sync_status ON inventory_item (sync_status)"))
        conn.commit()

def wipe_all_inventory(include_purchases=False):
    db_session.execute(text("DROP TABLE IF EXISTS inventory_item;"))
    db_session.execute(text("DROP TABLE IF EXISTS sale;"))
    db_session.execute(text("DROP TABLE IF EXISTS staging_item;"))
    if include_purchases:
        db_session.execute(text("DROP TABLE IF EXISTS purchase_record;"))
    db_session.commit()
    
    # VACUUM cannot be run within a transaction
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM;"))
        
    init_db()