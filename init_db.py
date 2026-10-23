import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/factory.db")
SCHEMA_PATH = Path("config/schema.sql")

def main():
    print("Initializing Database...")
    if not SCHEMA_PATH.exists():
        print(f"ERROR: {SCHEMA_PATH} not found!")
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(schema_sql)
        conn.commit()
        print("Schema executed successfully.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()

    expected = {"sensor_readings", "production_units", "anomalies", "system_config"}
    if expected.issubset(set(tables)):
        print(f"SUCCESS: All 4 tables created -> {tables}")
    else:
        print(f"MISSING TABLES: {expected - set(tables)}")

if __name__ == "__main__":
    main()