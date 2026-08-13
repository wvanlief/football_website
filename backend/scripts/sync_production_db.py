import sys
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, MetaData
from backend.database import Base

def sync_production_db(prod_url: str, local_url: str = "sqlite:///./football_games.db"):
    if prod_url.startswith("postgres://"):
        prod_url = prod_url.replace("postgres://", "postgresql://", 1)
        
    print(f"Connecting to production PostgreSQL database...")
    prod_engine = create_engine(prod_url)

    print(f"Connecting to local database ({local_url})...")
    if local_url.startswith("sqlite"):
        local_engine = create_engine(local_url, connect_args={"check_same_thread": False})
    else:
        local_engine = create_engine(local_url)

    print("Reflecting production schema...")
    prod_meta = MetaData()
    prod_meta.reflect(bind=prod_engine)

    print("Re-creating local schema...")
    Base.metadata.drop_all(bind=local_engine)
    Base.metadata.create_all(bind=local_engine)

    total_records = 0

    # Insert tables in dependency order
    for table in Base.metadata.sorted_tables:
        table_name = table.name
        if table_name in prod_meta.tables:
            prod_table = prod_meta.tables[table_name]
            with prod_engine.connect() as prod_conn:
                rows = prod_conn.execute(prod_table.select()).mappings().all()
                row_dicts = [dict(r) for r in rows]
                
                if row_dicts:
                    with local_engine.connect() as local_conn:
                        local_conn.execute(table.insert(), row_dicts)
                        local_conn.commit()
                    total_records += len(row_dicts)
                    print(f"  [OK] Copied {len(row_dicts)} records into table '{table_name}'")
                else:
                    print(f"  [OK] Table '{table_name}' is empty (0 records)")
        else:
            print(f"  [SKIP] Table '{table_name}' not found in production database")

    print(f"\n[COMPLETE] Sync complete! Total {total_records} records copied into local database ('{local_url}').")

if __name__ == "__main__":
    prod_db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if len(sys.argv) > 1:
        prod_db_url = sys.argv[1]

    if not prod_db_url or prod_db_url.startswith("sqlite"):
        print("Usage: python -m backend.scripts.sync_production_db <DATABASE_PUBLIC_URL>")
        print("Or set DATABASE_PUBLIC_URL in your .env file.")
        sys.exit(1)

    sync_production_db(prod_db_url)
