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
    return {name: _clean(pd.read_csv(Path(folder) / f"{name}.csv.gz")) for name in MARTS}


# ---------------------------------------------------------------- friendly wording

REASON_LABELS = {
    "overproduction": "Cooked but not sold",
    "expired": "Expired in storage",
    "expired_after_thaw": "Expired after thawing",
    "expired_frozen": "Expired in the freezer",
}
PURCHASE_LABELS = {"scheduled": "Regular restock", "emergency": "Urgent purchase"}
LOCATION_LABELS = {"mall": "Mall", "campus": "Campus", "canteen": "Canteen", "food_court": "Food court"}


def pretty_name(text):
    """beef_meat -> Beef Meat"""
    return str(text).replace("_", " ").title()


def prettify(marts):
    """Replace technical codes by plain words. Display only: the database is not touched."""
    out = {}
    for name, df in marts.items():
        df = df.copy()
        if "ingredient_name" in df.columns:
            df["ingredient_name"] = df["ingredient_name"].map(pretty_name)
        if "reason" in df.columns:
            df["reason"] = df["reason"].map(lambda x: REASON_LABELS.get(x, pretty_name(x)))
        if "purchase_type" in df.columns:
            df["purchase_type"] = df["purchase_type"].map(lambda x: PURCHASE_LABELS.get(x, pretty_name(x)))
        if "location_type" in df.columns:
            df["location_type"] = df["location_type"].map(lambda x: LOCATION_LABELS.get(x, pretty_name(x)))
        out[name] = df
    return out


def load_marts():
    """Use PostgreSQL when database settings exist, otherwise the CSV samples.

    Set DASHBOARD_SOURCE=csv or DASHBOARD_SOURCE=db to force one of them.
    """
    source = os.getenv("DASHBOARD_SOURCE")
    if source is None:
        source = "db" if os.getenv("POSTGRES_PASSWORD") else "csv"
    return prettify(load_from_db() if source == "db" else load_from_csv())


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
            purchases.loc[purchases["purchase_type"] == PURCHASE_LABELS["emergency"], "total_cost"].sum(),
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


def monthly_spend(purchases):
    month = purchases["date_day"].dt.strftime("%Y-%m")
    return purchases.groupby(month)["total_cost"].sum()


def top_purchases(purchases, top=10):
    return purchases.groupby("ingredient_name")["total_cost"].sum().sort_values(ascending=False).head(top)


# ---------------------------------------------------------------- v2: chart-ready tables

MILLION = 1e6


def weekly(df, how="sum"):
    """Daily table (date index) -> weekly table, weeks starting on Monday."""
    r = df.resample("W-MON", label="left", closed="left")
    return r.sum() if how == "sum" else r.mean()


def weekly_revenue_by_menu(sales):
    """Long table: week, menu, revenue in IDR million."""
    d = sales.pivot_table(index="date_day", columns="menu_name", values="revenue", aggfunc="sum").fillna(0)
    w = weekly(d) / MILLION
    # drop the first and last weeks when they are partial, so lines do not dip at the edges
    if len(w) > 2:
        w = w.iloc[1:-1]
    long = w.reset_index().melt(id_vars="date_day", var_name="Menu", value_name="Sales (IDR million)")
    return long.rename(columns={"date_day": "Week"})


def weekly_cooked_sold(prod):
    d = prod.groupby("date_day")[["portions_cooked", "portions_sold", "portions_wasted"]].sum()
    w = weekly(d)
    if len(w) > 2:
        w = w.iloc[1:-1]
    w = w.rename(columns={"portions_cooked": "Cooked", "portions_sold": "Sold", "portions_wasted": "Thrown away"})
    long = w.reset_index().melt(id_vars="date_day", var_name="Servings", value_name="Servings per week")
    return long.rename(columns={"date_day": "Week"})


def sales_by_outlet(sales, top=10):
    s = sales.groupby("outlet_name")["revenue"].sum().sort_values(ascending=False).head(top) / MILLION
    return s.rename("Sales (IDR million)").reset_index().rename(columns={"outlet_name": "Outlet"})


def hourly_long(hourly):
    h = hourly_profile(hourly).reset_index()
    h["Hour"] = h["order_hour"].map(lambda x: f"{int(x):02d}:00")
    return h.melt(id_vars=["order_hour", "Hour"], var_name="Day type", value_name="Servings per outlet per day")


def throw_away_by_outlet(prod, top=10):
    s = waste_rate_by_outlet(prod, top).rename("Thrown away (% of cooked)")
    return s.reset_index().rename(columns={"outlet_name": "Outlet"})


def waste_cost_by_ingredient(waste, top=10):
    s = top_waste_ingredients(waste, top) / MILLION
    return s.rename("Cost of food thrown away (IDR million)").reset_index().rename(columns={"ingredient_name": "Ingredient"})


def waste_cost_outlet_month(waste):
    """Cost of thrown-away food per outlet and month, in IDR million (for the heatmap)."""
    t = waste.assign(Month=waste["date_day"].dt.strftime("%Y-%m")).groupby(["outlet_name", "Month"])["waste_cost"].sum()
    t = (t / MILLION).rename("IDR million").reset_index().rename(columns={"outlet_name": "Outlet"})
    return t


def monthly_spend_table(purchases):
    """Monthly spend split by regular vs urgent purchases, in IDR million."""
    month = purchases["date_day"].dt.strftime("%Y-%m")
    t = purchases.groupby([month.rename("Month"), "purchase_type"])["total_cost"].sum() / MILLION
    return t.rename("Spend (IDR million)").reset_index().rename(columns={"purchase_type": "Type"})


def spend_by_ingredient(purchases, top=10):
    s = top_purchases(purchases, top) / MILLION
    return s.rename("Spend (IDR million)").reset_index().rename(columns={"ingredient_name": "Ingredient"})


def month_over_month(sales, column="revenue"):
    """Percent change in average daily value, last full month vs the month before; None if not available."""
    if sales.empty:
        return None
    d = sales.groupby("date_day")[column].sum()
    last_day = d.index.max()
    if last_day != last_day + pd.offsets.MonthEnd(0):  # last month incomplete
        d = d[d.index < last_day.replace(day=1)]
    if d.empty:
        return None
    m = d.groupby(d.index.to_period("M")).mean()  # daily average, so short months compare fairly
    if len(m) < 2 or m.iloc[-2] == 0:
        return None
    return float((m.iloc[-1] / m.iloc[-2] - 1) * 100)


def summary_sentences(f):
    """Three plain-English sentences describing the selected data."""
    sales, prod = f["mart_daily_sales"], f["mart_daily_production"]
    k = kpis(f)
    start, end = sales["date_day"].min(), sales["date_day"].max()
    top_menu = sales.groupby("menu_name")["portions"].sum().idxmax()
    top_outlet = sales.groupby("outlet_name")["revenue"].sum().idxmax()
    hourly = f["mart_hourly_sales"].groupby("order_hour")["portions"].sum()
    peak = int(hourly.idxmax()) if not hourly.empty else None
    rates = waste_rate_by_outlet(prod, 1)
    worst = rates.index[0] if len(rates) else "n/a"
    s1 = (f"From {start:%d %b %Y} to {end:%d %b %Y}, the selected outlets sold {k['portions_sold']:,.0f} servings "
          f"and made IDR {k['revenue'] / MILLION:,.0f} million in sales.")
    s2 = (f"{top_menu} is the best seller, {top_outlet} brings in the most sales"
          + (f", and the busiest hour is {peak:02d}:00." if peak is not None else "."))
    s3 = (f"About {k['waste_rate_pct']:.1f}% of the food we cook is thrown away "
          f"(IDR {k['wasted_food_cost'] / MILLION:,.1f} million), most at {worst}.")
    return [s1, s2, s3]


# ---------------------------------------------------------------- forecast tab

STRATEGIES = {
    "Kitchen today": "kitchen_plan",
    "Kitchen rule (no human error)": "rule_plan",
    "ML model": "model_plan",
}
FORECAST_COLUMNS = {
    "Actual sales": "actual",
    "ML model": "model_forecast",
    "Kitchen rule": "rule_forecast",
}
FEATURE_LABELS = {
    "day_of_week": "Day of the week",
    "location_type": "Type of location",
    "mean_28": "Average of the last 4 weeks",
    "mean_14": "Average of the last 2 weeks",
    "mean_7": "Average of the last week",
    "is_payday": "Payday period",
    "lag_7": "Same day last week",
    "lag_14": "Same day 2 weeks ago",
    "lag_1": "Yesterday",
    "trend_ratio": "Recent trend",
    "same_weekday_mean_4": "Same weekday, last 4 weeks",
    "is_holiday": "Public holiday",
    "is_weekend": "Weekend",
    "day_of_month": "Day of the month",
    "month": "Month",
    "outlet_id": "Which outlet",
    "menu_id": "Which menu",
}


def load_ml(folder=SAMPLE_DIR):
    """Predictions and summary written by ml/train.py. Returns (None, None) if not there yet."""
    import json

    pred_file, summary_file = Path(folder) / "ml_predictions.csv.gz", Path(folder) / "ml_summary.json"
    if not (pred_file.exists() and summary_file.exists()):
        return None, None
    pred = pd.read_csv(pred_file, parse_dates=["date_day"])
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    return pred, summary


def filter_predictions(pred, outlet_ids, menu_names):
    return pred[pred["outlet_id"].isin(outlet_ids) & pred["menu_name"].isin(menu_names)]


def forecast_accuracy(pred):
    """Total absolute error as a share of total sales (lower is better)."""
    actual = pred["actual"].sum()
    return {
        "ML model": (pred["actual"] - pred["model_forecast"]).abs().sum() / actual * 100,
        "Kitchen rule": (pred["actual"] - pred["rule_forecast"]).abs().sum() / actual * 100,
        "Same day last week": (pred["actual"] - pred["last_week"]).abs().sum() / actual * 100,
    }


def money_simulation(pred):
    """Waste cost and missed profit for each cooking plan (missed demand = lost sale)."""
    rows = []
    for name, col in STRATEGIES.items():
        wasted = (pred[col] - pred["actual"]).clip(lower=0)
        unmet = (pred["actual"] - pred[col]).clip(lower=0)
        rows.append({
            "Plan": name,
            "Wasted food": float((wasted * pred["waste_cost_per_portion"]).sum()),
            "Missed profit": float((unmet * pred["lost_profit_per_portion"]).sum()),
            "Served": float(1 - unmet.sum() / pred["actual"].sum()) * 100,
        })
    out = pd.DataFrame(rows)
    out["Total"] = out["Wasted food"] + out["Missed profit"]
    return out


def money_long(sim):
    """Long table in IDR million for the stacked bars."""
    long = sim.melt(id_vars="Plan", value_vars=["Wasted food", "Missed profit"], var_name="Cost", value_name="IDR million")
    long["IDR million"] = long["IDR million"] / MILLION
    return long


def daily_forecast_long(pred):
    d = pred.groupby("date_day")[list(FORECAST_COLUMNS.values())].sum()
    d = d.rename(columns={v: k for k, v in FORECAST_COLUMNS.items()})
    long = d.reset_index().melt(id_vars="date_day", var_name="Series", value_name="Servings per day")
    return long.rename(columns={"date_day": "Date"})


def importance_table(summary):
    share = pd.Series(summary["importance_pct"]).round(1)
    out = share.rename("Share of influence (%)").reset_index()
    out["index"] = out["index"].map(lambda f: FEATURE_LABELS.get(f, f))
    return out.rename(columns={"index": "What the model looks at"})
