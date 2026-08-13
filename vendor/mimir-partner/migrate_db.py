import sqlite3
import os
import sys

def migrate():
    """Manual migration script using sqlite3 to update the database schema."""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(application_path, 'card_shop.db')
    
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found. Please run main.py once to initialize the database.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def add_column_if_missing(table, column, definition):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"Added column {column} to {table}.")
        except sqlite3.OperationalError:
            # Column likely already exists
            pass

    # 1. Update tables individually
    print("Checking table schemas...")
    add_column_if_missing("inventory_item", "date_added", "DATETIME")
    add_column_if_missing("inventory_item", "needs_update", "BOOLEAN DEFAULT 0")
    add_column_if_missing("inventory_item", "old_price", "FLOAT DEFAULT NULL")
    add_column_if_missing("inventory_item", "set_name", "VARCHAR(100)")
    add_column_if_missing("inventory_item", "sequence_number", "VARCHAR(50)")
    add_column_if_missing("inventory_item", "card_type", "VARCHAR(50)")
    add_column_if_missing("inventory_item", "variant", "VARCHAR(50)")
    add_column_if_missing("inventory_item", "condition", "VARCHAR(50)")
    add_column_if_missing("inventory_item", "needs_review", "BOOLEAN DEFAULT 0")
    add_column_if_missing("inventory_item", "image_url", "VARCHAR(255)")
    add_column_if_missing("inventory_item", "image_locked", "BOOLEAN DEFAULT 0")
    add_column_if_missing("inventory_item", "sync_status", "VARCHAR(50) DEFAULT 'paused'")
    add_column_if_missing("inventory_item", "custom_image_url", "VARCHAR(255)")
    add_column_if_missing("inventory_item", "shop_listing_price", "FLOAT DEFAULT NULL")
    add_column_if_missing("inventory_item", "sticker_price", "FLOAT DEFAULT NULL")
    add_column_if_missing("inventory_item", "paused_stock", "INTEGER DEFAULT 0")

    add_column_if_missing("staging_item", "sequence_number", "VARCHAR(50)")
    add_column_if_missing("staging_item", "set_name", "VARCHAR(100)")
    add_column_if_missing("staging_item", "card_type", "VARCHAR(50)")
    add_column_if_missing("staging_item", "variant", "VARCHAR(50)")
    add_column_if_missing("staging_item", "condition", "VARCHAR(50)")
    add_column_if_missing("staging_item", "quantity", "INTEGER DEFAULT 1")
    add_column_if_missing("staging_item", "image_path", "VARCHAR(255)")
    add_column_if_missing("staging_item", "needs_review", "BOOLEAN DEFAULT 0")
    add_column_if_missing("staging_item", "ocr_metadata", "TEXT DEFAULT '{}'")
    add_column_if_missing("staging_item", "barcode_path", "VARCHAR(255)")
    add_column_if_missing("staging_item", "image_locked", "BOOLEAN DEFAULT 0")

    # 2. Update sale table
    print("Updating Sale table...")
    add_column_if_missing("sale", "transaction_type", "VARCHAR(20)")
    add_column_if_missing("sale", "trade_in_value", "FLOAT DEFAULT 0.0")
    add_column_if_missing("sale", "processing_fees", "FLOAT DEFAULT 0.0")
    add_column_if_missing("sale", "trade_credit_deduction", "FLOAT DEFAULT 0.0")
    add_column_if_missing("sale", "net_revenue", "FLOAT DEFAULT 0.0")

    # Update sync_outbox table
    print("Updating sync_outbox table...")
    add_column_if_missing("sync_outbox", "new_price", "FLOAT DEFAULT NULL")
    add_column_if_missing("sync_outbox", "sync_status", "VARCHAR(50) DEFAULT 'pending'")

    # 3. Create purchase_record table
    print("Checking new tables...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_queue_item (
            id INTEGER PRIMARY KEY,
            sku VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            set_name VARCHAR(100),
            sequence_number VARCHAR(50),
            cost FLOAT NOT NULL,
            price FLOAT NOT NULL,
            old_price FLOAT,
            card_type VARCHAR(50),
            variant VARCHAR(50),
            condition VARCHAR(50),
            stock INTEGER DEFAULT 0,
            last_sync DATETIME,
            date_added DATETIME,
            needs_update BOOLEAN DEFAULT 0,
            needs_review BOOLEAN DEFAULT 0,
            image_url VARCHAR(255),
            image_locked BOOLEAN DEFAULT 0,
            sync_status VARCHAR(50) DEFAULT 'paused',
            custom_image_url VARCHAR(255),
            shop_listing_price FLOAT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS online_pull_queue (
            id INTEGER PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            order_id VARCHAR(100),
            status VARCHAR(50) DEFAULT 'pending_pull',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_outbox (
            id INTEGER PRIMARY KEY,
            action_type VARCHAR(50) NOT NULL,
            sku VARCHAR(50) NOT NULL,
            quantity_change INTEGER NOT NULL,
            new_price FLOAT,
            sync_status VARCHAR(50) DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipping_rule (
            id INTEGER PRIMARY KEY,
            min_price FLOAT NOT NULL,
            max_price FLOAT NOT NULL,
            additional_cost FLOAT NOT NULL,
            card_type VARCHAR(50) DEFAULT 'Card'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_record (
            id INTEGER PRIMARY KEY,
            sku VARCHAR(50),
            quantity INTEGER DEFAULT 1,
            cost_per_unit FLOAT,
            timestamp DATETIME
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS show_price_capture (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            item_count INTEGER DEFAULT 0,
            total_value FLOAT DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS show_price_capture_item (
            id INTEGER PRIMARY KEY,
            capture_id INTEGER NOT NULL,
            sku VARCHAR(50) NOT NULL,
            sticker_price FLOAT NOT NULL,
            FOREIGN KEY(capture_id) REFERENCES show_price_capture(id)
        )
    """)

    # 4. Check system_settings table
    print("Checking system_settings table...")
    add_column_if_missing("system_settings", "resticker_threshold", "FLOAT DEFAULT 2.00")
    add_column_if_missing("system_settings", "sim_mode", "BOOLEAN DEFAULT 0")

    # 4. Create system_settings table
    print("Checking system_settings table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY,
            price_fluctuation_threshold FLOAT DEFAULT 0.10,
            rounding_strategy VARCHAR(50) DEFAULT 'Keep Raw TCG Decimal Payouts',
            paperweight_days INTEGER DEFAULT 60,
            buy_percentage FLOAT DEFAULT 0.70,
            trade_percentage FLOAT DEFAULT 0.80,
            ocr_x INTEGER DEFAULT 0,
            ocr_y INTEGER DEFAULT 0,
            ocr_width INTEGER DEFAULT 0,
            ocr_height INTEGER DEFAULT 0,
            sync_folder VARCHAR(255),
            markup_type VARCHAR(50) DEFAULT 'Percentage (%)',
            markup_value FLOAT DEFAULT 0.0,
            rounding_rule VARCHAR(50) DEFAULT 'Exact/None'
        )
    """)
    add_column_if_missing("system_settings", "sync_folder", "VARCHAR(255)")
    add_column_if_missing("system_settings", "markup_type", "VARCHAR(50) DEFAULT 'Percentage (%)'")
    add_column_if_missing("system_settings", "markup_value", "FLOAT DEFAULT 0.0")
    add_column_if_missing("system_settings", "rounding_rule", "VARCHAR(50) DEFAULT 'Exact/None'")

    add_column_if_missing("system_settings", "rounding_strategy", "VARCHAR(50) DEFAULT 'Keep Raw TCG Decimal Payouts'")
    add_column_if_missing("system_settings", "ocr_x", "INTEGER DEFAULT 0")
    add_column_if_missing("system_settings", "ocr_y", "INTEGER DEFAULT 0")
    add_column_if_missing("system_settings", "ocr_width", "INTEGER DEFAULT 0")
    add_column_if_missing("system_settings", "ocr_height", "INTEGER DEFAULT 0")
    add_column_if_missing("system_settings", "omit_graded_from_recon", "BOOLEAN DEFAULT 0")
    add_column_if_missing("system_settings", "graded_wizard_sales_count", "INTEGER DEFAULT 5")
    add_column_if_missing("system_settings", "graded_wizard_omit_diff", "FLOAT DEFAULT 20.0")
    add_column_if_missing("system_settings", "gmail_monitor_enabled", "BOOLEAN DEFAULT 0")
    add_column_if_missing("system_settings", "gmail_address", "VARCHAR(100) DEFAULT ''")
    add_column_if_missing("system_settings", "gmail_app_password", "VARCHAR(100) DEFAULT ''")
    add_column_if_missing("system_settings", "gmail_folder", "VARCHAR(100) DEFAULT 'INBOX'")

    # 4. Data Repair: Ensure existing rows don't have NULLs for numeric fields
    print("Repairing NULL values in database...")
    cursor.execute("UPDATE system_settings SET buy_percentage = 0.70 WHERE buy_percentage IS NULL")
    cursor.execute("UPDATE system_settings SET trade_percentage = 0.80 WHERE trade_percentage IS NULL")
    cursor.execute("UPDATE system_settings SET price_fluctuation_threshold = 0.10 WHERE price_fluctuation_threshold IS NULL")
    cursor.execute("UPDATE system_settings SET rounding_strategy = 'Keep Raw TCG Decimal Payouts' WHERE rounding_strategy IS NULL")
    cursor.execute("UPDATE system_settings SET resticker_threshold = 2.00 WHERE resticker_threshold IS NULL")
    cursor.execute("UPDATE system_settings SET markup_value = 0.0 WHERE markup_value IS NULL")
    cursor.execute("UPDATE system_settings SET ocr_x = 0 WHERE ocr_x IS NULL")
    cursor.execute("UPDATE system_settings SET ocr_y = 0 WHERE ocr_y IS NULL")
    cursor.execute("UPDATE system_settings SET ocr_width = 0 WHERE ocr_width IS NULL")
    cursor.execute("UPDATE system_settings SET ocr_height = 0 WHERE ocr_height IS NULL")
    
    # Ensure Inventory items have a date_added if they were created before this column
    cursor.execute("UPDATE inventory_item SET date_added = CURRENT_TIMESTAMP WHERE date_added IS NULL")
    cursor.execute("UPDATE inventory_item SET price = 0.0 WHERE price IS NULL")
    cursor.execute("UPDATE inventory_item SET shop_listing_price = price WHERE shop_listing_price IS NULL")
    cursor.execute("UPDATE inventory_item SET sticker_price = price WHERE sticker_price IS NULL")

    # 4. Insert default row if empty
    cursor.execute("SELECT COUNT(*) FROM system_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO system_settings (id, price_fluctuation_threshold, rounding_strategy, paperweight_days, buy_percentage, trade_percentage)
            VALUES (1, 0.10, 'Keep Raw TCG Decimal Payouts', 60, 0.70, 0.80)
        """)
        print("Default system settings row inserted.")

    conn.commit()
    conn.close()
    print("Migration process complete.")

if __name__ == "__main__":
    migrate()