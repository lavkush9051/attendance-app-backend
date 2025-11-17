from sqlalchemy import create_engine, text
from app.database import DATABASE_URL

def check_tables():
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Tables to check
    tables = [
        'emp_shift_tbl',
        'employee_tbl',
        'clockin_clockout_tbl'
    ]
    
    with engine.connect() as connection:
        for table in tables:
            print(f"\n=== Data in {table} ===")
            result = connection.execute(text(f"SELECT * FROM {table}"))
            rows = result.fetchall()
            if rows:
                # Print column names
                print("Columns:", result.keys())
                # Print each row
                for row in rows:
                    print(row)
            else:
                print("No data found")

if __name__ == "__main__":
    check_tables()