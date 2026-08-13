import sqlite3
import os
import sys

def migrate_db():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    db_path = os.path.join(application_path, 'card_shop.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables_to_update = ['inventory_item', 'review_queue_item', 'sale', 'staging_item']
    
    for table in tables_to_update:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN game VARCHAR(50) DEFAULT 'Pokemon'")
            print(f"Added 'game' column to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"'game' column already exists in {table}")
            else:
                print(f"Error updating {table}: {e}")
                
        # Backfill existing records
        try:
            cursor.execute(f"UPDATE {table} SET game = 'Pokemon' WHERE game IS NULL")
        except Exception as e:
            pass

    try:
        cursor.execute("ALTER TABLE system_settings ADD COLUMN pokemon_icon_url VARCHAR(255) DEFAULT ''")
        print("Added 'pokemon_icon_url' to system_settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            print(f"Error updating system_settings: {e}")

    try:
        cursor.execute("ALTER TABLE system_settings ADD COLUMN one_piece_icon_url VARCHAR(255) DEFAULT ''")
        print("Added 'one_piece_icon_url' to system_settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            print(f"Error updating system_settings: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
