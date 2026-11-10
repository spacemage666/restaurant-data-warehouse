"""Turn the daily sales mart into a supervised learning table.

One row = one outlet, one menu item, one day. The target is the number of portions sold.
Every feature only uses information that is known at the end of the previous day, so the
model never peeks into the future.
"""
import numpy as np
import pandas as pd

KEYS = ["outlet_id", "menu_id"]
CATEGORICAL = ["outlet_id", "menu_id", "location_type"]
NUMERIC = [
    "lag_1", "lag_7", "lag_14",
    "mean_7", "mean_14", "mean_28", "same_weekday_mean_4", "trend_ratio",
    "day_of_week", "is_weekend", "day_of_month", "month", "is_payday",
]
# is_holiday is built below but not used as a feature: the data has only three holidays
# (two quiet, one busy), too few for the model to learn how a holiday changes sales.
# With it, the model predicted a quiet Christmas when the real day was busy.
FEATURES = CATEGORICAL + NUMERIC
WARMUP_DAYS = 28  # rolling windows need 28 days of history


def build_dataset(sales, production, holidays):
    """Full outlet x menu x day table with features, target and the kitchen's own numbers."""
    dates = pd.date_range(sales["date_day"].min(), sales["date_day"].max())
    outlets = sales[["outlet_id", "outlet_name", "location_type"]].drop_duplicates("outlet_id")
    menus = sales[["menu_id", "menu_name"]].drop_duplicates("menu_id")

    grid = pd.MultiIndex.from_product(
        [outlets["outlet_id"], menus["menu_id"], dates], names=KEYS + ["date_day"]
    ).to_frame(index=False)
    daily = sales.groupby(KEYS + ["date_day"], as_index=False)["portions"].sum()
    df = grid.merge(daily, on=KEYS + ["date_day"], how="left")
    df["portions"] = df["portions"].fillna(0.0)
    df = df.sort_values(KEYS + ["date_day"]).reset_index(drop=True)

    g = df.groupby(KEYS)["portions"]
    for k in (1, 7, 14, 21, 28):
        df[f"lag_{k}"] = g.shift(k)
    df["prev"] = g.shift(1)
    for w in (7, 14, 28):
        df[f"mean_{w}"] = df.groupby(KEYS)["prev"].transform(
            lambda s, w=w: s.rolling(w, min_periods=w).mean()
        )
    df["same_weekday_mean_4"] = df[["lag_7", "lag_14", "lag_21", "lag_28"]].mean(axis=1)
    df["trend_ratio"] = df["mean_7"] / df["mean_28"].clip(lower=1)

    d = df["date_day"]
    df["day_of_week"] = d.dt.dayofweek
    df["is_weekend"] = (d.dt.dayofweek >= 5).astype(int)
    df["day_of_month"] = d.dt.day
    df["month"] = d.dt.month
    df["is_payday"] = ((d.dt.day >= 25) | (d.dt.day <= 3)).astype(int)
    df["is_holiday"] = d.dt.strftime("%Y-%m-%d").isin(holidays).astype(int)

    df = df.merge(outlets, on="outlet_id").merge(menus, on="menu_id")
    for col in CATEGORICAL:
        df[col] = df[col].astype("category")

    # numbers from the current kitchen routine (used as the baseline)
    kitchen = production[KEYS + ["date_day", "portions_forecast", "portions_planned"]]
    df = df.merge(kitchen, on=KEYS + ["date_day"], how="left")

    df["level"] = df["mean_28"].clip(lower=1.0)  # typical size of this outlet and menu
    df = df.drop(columns=["prev", "lag_21", "lag_28"])
    return df[df["mean_28"].notna()].reset_index(drop=True)


def split_by_date(df, val_start, test_start):
    """Time-based split: train < val_start <= validation < test_start <= test."""
    val_start, test_start = pd.Timestamp(val_start), pd.Timestamp(test_start)
    train = df[df["date_day"] < val_start]
    val = df[(df["date_day"] >= val_start) & (df["date_day"] < test_start)]
    test = df[df["date_day"] >= test_start]
    return train, val, test
