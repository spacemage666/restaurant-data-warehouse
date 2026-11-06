"""Data loading and metric helpers for the dashboard (no Streamlit code here)."""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"

MARTS = [
    "mart_daily_sales",
    "mart_hourly_sales",
    "mart_daily_production",
    "mart_waste_by_ingredient",
    "mart_purchases_by_ingredient",
]

load_dotenv(ROOT_DIR / ".env")


# ---------------------------------------------------------------- loading

def _clean(df):
    """Make sure dates are datetimes and numeric columns are floats."""
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
    """Read the gold marts from PostgreSQL (connection settings come from .env)."""
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
    """Read the marts from CSV files (used when no database is available)."""
    return {name: _clean(pd.read_csv(Path(folder) / f"{name}.csv")) for name in MARTS}


def load_marts():
    """Use PostgreSQL when database settings exist, otherwise the CSV samples.

    Set DASHBOARD_SOURCE=csv or DASHBOARD_SOURCE=db to force one of them.
    """
    source = os.getenv("DASHBOARD_SOURCE")
    if source is None:
        source = "db" if os.getenv("POSTGRES_PASSWORD") else "csv"
    return load_from_db() if source == "db" else load_from_csv()


# ---------------------------------------------------------------- filters

def outlet_table(marts):
    cols = ["outlet_id", "outlet_name", "location_type"]
    return marts["mart_daily_sales"][cols].drop_duplicates().sort_values("outlet_id")


def apply_filters(marts, start, end, outlet_ids, menu_names):
    """Filter every mart by date range and outlets; menus apply where a menu column exists."""
    filtered = {}
    for name, df in marts.items():
        mask = (df["date_day"] >= start) & (df["date_day"] <= end) & df["outlet_id"].isin(outlet_ids)
        if "menu_name" in df.columns:
            mask &= df["menu_name"].isin(menu_names)
        filtered[name] = df[mask]
    return filtered


# ---------------------------------------------------------------- metrics

def _ratio(a, b):
    return float(a) / float(b) * 100 if b else 0.0


def kpis(f):
    sales = f["mart_daily_sales"]
    prod = f["mart_daily_production"]
    purchases = f["mart_purchases_by_ingredient"]
    revenue = sales["revenue"].sum()
    gross_profit = sales["gross_profit"].sum()
    return {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "gross_margin_pct": _ratio(gross_profit, revenue),
        "portions_sold": sales["portions"].sum(),
        "waste_rate_pct": _ratio(prod["portions_wasted"].sum(), prod["portions_cooked"].sum()),
        "wasted_food_cost": prod["wasted_food_cost"].sum(),
        "emergency_share_pct": _ratio(
            purchases.loc[purchases["purchase_type"] == "emergency", "total_cost"].sum(),
            purchases["total_cost"].sum(),
        ),
    }


def fmt_idr(x):
    x = float(x)
    if abs(x) >= 1e9:
        return f"IDR {x / 1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"IDR {x / 1e6:,.1f}M"
    return f"IDR {x:,.0f}"


def daily_revenue_by_menu(sales):
    return sales.pivot_table(index="date_day", columns="menu_name", values="revenue", aggfunc="sum").fillna(0)


def revenue_by_outlet(sales, top=10):
    return sales.groupby("outlet_name")["revenue"].sum().sort_values(ascending=False).head(top)


def menu_margin_table(sales):
    t = sales.groupby("menu_name")[["portions", "revenue", "gross_profit"]].sum()
    t["gross_margin_pct"] = (t["gross_profit"] / t["revenue"] * 100).round(1)
    return t.sort_values("revenue", ascending=False)


def hourly_profile(hourly):
    """Average portions sold per outlet and day, for each hour, weekday vs weekend."""
    days = hourly.drop_duplicates(["date_day", "outlet_id"]).groupby("is_weekend").size()
    totals = hourly.groupby(["order_hour", "is_weekend"])["portions"].sum().unstack("is_weekend").fillna(0)
    profile = totals / days
    return profile.rename(columns={False: "Weekday", True: "Weekend"})


def cooked_vs_sold(prod):
    return prod.groupby("date_day")[["portions_cooked", "portions_sold", "portions_wasted"]].sum()


def waste_rate_by_outlet(prod, top=10):
    g = prod.groupby("outlet_name")[["portions_wasted", "portions_cooked"]].sum()
    return (g["portions_wasted"] / g["portions_cooked"] * 100).sort_values(ascending=False).head(top)


def daily_waste_cost(waste):
    return waste.groupby("date_day")["waste_cost"].sum()


def top_waste_ingredients(waste, top=10):
    return waste.groupby("ingredient_name")["waste_cost"].sum().sort_values(ascending=False).head(top)


def waste_by_reason(waste):
    t = waste.groupby("reason")["waste_cost"].sum().sort_values(ascending=False).to_frame()
    total = t["waste_cost"].sum()
    t["share_pct"] = (t["waste_cost"] / total * 100).round(1) if total else 0.0
    return t


def spend_by_type(purchases):
    return purchases.groupby("purchase_type")["total_cost"].sum().sort_values(ascending=False)


def top_purchases(purchases, top=10):
    return purchases.groupby("ingredient_name")["total_cost"].sum().sort_values(ascending=False).head(top)
