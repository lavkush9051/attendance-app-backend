"""
Migration script to add SAP sync tracking columns to leave_request_tbl.

Adds:
  - sap_sync_status (varchar(20), default 'PENDING')
  - sap_sync_timestamp (timestamp with time zone, nullable)

Usage:
  python migrate_leave_sap_columns.py
"""

from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        # Check if columns already exist
        check_sql = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'leave_request_tbl' 
            AND column_name IN ('sap_sync_status', 'sap_sync_timestamp')
        """)
        result = conn.execute(check_sql)
        existing_cols = {row[0] for row in result}

        # Add sap_sync_status if missing
        if 'sap_sync_status' not in existing_cols:
            print("Adding column: sap_sync_status")
            conn.execute(text("""
                ALTER TABLE leave_request_tbl 
                ADD COLUMN sap_sync_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
            """))
            conn.commit()
            print("✅ sap_sync_status column added")
        else:
            print("ℹ️  sap_sync_status already exists")

        # Add sap_sync_timestamp if missing
        if 'sap_sync_timestamp' not in existing_cols:
            print("Adding column: sap_sync_timestamp")
            conn.execute(text("""
                ALTER TABLE leave_request_tbl 
                ADD COLUMN sap_sync_timestamp TIMESTAMP WITH TIME ZONE
            """))
            conn.commit()
            print("✅ sap_sync_timestamp column added")
        else:
            print("ℹ️  sap_sync_timestamp already exists")

    print("\n✅ Migration completed successfully")

if __name__ == "__main__":
    migrate()
