import sys
import os

# Add trialapp directory to path so we can import db
sys.path.append(r"c:\Users\Denisha\Desktop\trialapp")
from db import get_db_connection
from datetime import datetime, timedelta

def migrate():
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to connect to database.")
            return

        cursor = conn.cursor()
        print("Adding expires_at column to voting_tokens table...")
        
        # Check if column exists first to avoid crashing
        cursor.execute("SHOW COLUMNS FROM voting_tokens LIKE 'expires_at'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE voting_tokens ADD COLUMN expires_at DATETIME;")
            conn.commit()
            print("Successfully added expires_at column.")
            
            # Update existing tokens so they dont crash
            now_plus_15 = datetime.now() + timedelta(minutes=15)
            cursor.execute("UPDATE voting_tokens SET expires_at = %s WHERE expires_at IS NULL", (now_plus_15,))
            conn.commit()
            print("Updated existing tokens with a default 15m expiration.")
        else:
            print("Column expires_at already exists. No action taken.")

    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(r"c:\Users\Denisha\Desktop\trialapp\.env")
    migrate()
