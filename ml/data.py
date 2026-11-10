"""Load the gold marts needed by the forecasting model.

Reads from PostgreSQL when POSTGRES_PASSWORD is set (see .env), otherwise from the
CSV samples in dashboard/sample_data. Set ML_SOURCE=csv or ML_SOURCE=db to force one.
"""
import os
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT_DIR / "dashboard" / "sample_data"
MARTS = ["mart_daily_sales", "mart_daily_production"]

load_dotenv(ROOT_DIR / ".env")


def _clean(df):
    df = df.copy()
    for col in df.columns:
        if col == "date_day":
            df[col] = pd.to_datetime(df[col])
        elif df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass
    return df


def load_from_db():
    import psycopg

    marts = {}
    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:
            for name in MARTS:
                cur.execute(f"SELECT * FROM gold.{name}")
                columns = [c.name for c in cur.description]
                marts[name] = _clean(pd.DataFrame(cur.fetchall(), columns=columns))
    return marts


def load_from_csv(folder=SAMPLE_DIR):
    return {name: _clean(pd.read_csv(Path(folder) / f"{name}.csv.gz")) for name in MARTS}


def load_marts(folder=None):
    """Return {mart name: DataFrame}. A folder forces the CSV source."""
    if folder is not None:
        return load_from_csv(folder)
    source = os.getenv("ML_SOURCE") or ("db" if os.getenv("POSTGRES_PASSWORD") else "csv")
    return load_from_db() if source == "db" else load_from_csv()


def load_holidays():
    """Public holidays are known in advance, so the model may use them as a feature."""
    with open(ROOT_DIR / "data_generator" / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {str(h["date"]) for h in cfg["demand"].get("holidays", [])}
