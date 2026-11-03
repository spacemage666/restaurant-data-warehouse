"""Load the generated CSV files from data/raw into the PostgreSQL bronze schema.

The load is a full refresh: each table is truncated and reloaded inside a
single transaction, so a failed run leaves the previous data untouched.
"""
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"

TABLES = [
    "outlets",
    "ingredients",
    "menu_items",
    "recipes",
    "orders",
    "order_items",
    "production_logs",
    "purchases",
    "waste_logs",
]


def get_connection():
    load_dotenv(ROOT_DIR / ".env")
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def load_table(cur, table):
    path = RAW_DIR / f"{table}.csv"
    if not path.exists():
        sys.exit(f"Missing file: {path}. Run the generators first.")

    with open(path, encoding="utf-8") as f:
        columns = f.readline().strip().split(",")

    cur.execute(f"TRUNCATE bronze.{table}")
    copy_sql = (
        f"COPY bronze.{table} ({', '.join(columns)}) "
        "FROM STDIN WITH (FORMAT csv, HEADER true)"
    )
    with cur.copy(copy_sql) as copy, open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            copy.write(chunk)

    cur.execute(f"SELECT count(*) FROM bronze.{table}")
    return cur.fetchone()[0]


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in TABLES:
                n = load_table(cur, table)
                print(f"bronze.{table}: {n} rows")
    print("Done.")


if __name__ == "__main__":
    main()