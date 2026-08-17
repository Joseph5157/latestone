#!/usr/bin/env python3
"""Quick script to check databases and tables in Docker PostgreSQL."""

import os
from sqlalchemy import create_engine, text
from config.settings import get_settings

def main():
    settings = get_settings()
    db_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Get all databases
            result = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"))
            databases = result.fetchall()
            
            print("=" * 50)
            print("DATABASES")
            print("=" * 50)
            for db in databases:
                print(f"  • {db[0]}")
            
            # Get schemas in current database
            result = conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema') ORDER BY schema_name"))
            schemas = result.fetchall()
            
            print(f"\n{'=' * 50}")
            print(f"SCHEMAS in '{settings.POSTGRES_DB}'")
            print("=" * 50)
            for schema in schemas:
                print(f"  • {schema[0]}")
            
            # Get tables in plant_monitoring schema
            result = conn.execute(text(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{settings.PLANT_MONITORING_SCHEMA}' ORDER BY table_name"))
            tables = result.fetchall()
            
            print(f"\n{'=' * 50}")
            print(f"TABLES in '{settings.PLANT_MONITORING_SCHEMA}' schema")
            print("=" * 50)
            if tables:
                for table in tables:
                    print(f"  • {table[0]}")
                
                # Get row counts
                print(f"\n{'=' * 50}")
                print("ROW COUNTS")
                print("=" * 50)
                for table in tables:
                    table_name = table[0]
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {settings.PLANT_MONITORING_SCHEMA}.{table_name}"))
                    count = result.scalar()
                    print(f"  {table_name:20s}: {count:>12,} rows")
            else:
                print("  (No tables found - schema may not be seeded yet)")
        
        print("\n✓ Connection successful!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
