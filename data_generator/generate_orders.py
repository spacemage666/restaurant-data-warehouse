"""Generate daily sales data: orders and order_items."""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR.parent / "data" / "raw"


def load_config():
    with open(BASE_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize(weights):
    """Turn a dict of weights into (keys, probabilities that sum to 1)."""
    keys = list(weights)
    probs = np.array(list(weights.values()), dtype=float)
    return keys, probs / probs.sum()


def calendar_factor(demand, date, start):
    """Optional effects on top of the weekday/weekend pattern.

    All keys are optional; without them the factor is 1.0.
      monthly_growth: demand growth per month (0.02 = +2% each month)
      payday_boost:   extra demand on days 25-31 and 1-3 of each month
      holidays:       list of {date: "YYYY-MM-DD", multiplier: x}
    """
    factor = 1.0
    months = (date.year - start.year) * 12 + (date.month - start.month)
    factor *= (1 + demand.get("monthly_growth", 0.0)) ** months
    if date.day >= 25 or date.day <= 3:
        factor *= 1 + demand.get("payday_boost", 0.0)
    holidays = {str(h["date"]): h["multiplier"] for h in demand.get("holidays", [])}
    factor *= holidays.get(date.strftime("%Y-%m-%d"), 1.0)
    return factor


def outlet_base_orders(demand, outlets, seed):
    """Average weekday orders per outlet.

    With demand.outlet_orders in the config, every outlet gets its own level:
    a few small outlets (small_min..small_max) and the rest between min..max.
    Busier location types (higher traffic_multiplier) get the higher levels.
    Without that block, every outlet uses base_orders_per_day * traffic_multiplier.
    """
    spec = demand.get("outlet_orders")
    if not spec:
        return {int(r.outlet_id): demand["base_orders_per_day"] * r.traffic_multiplier
                for r in outlets.itertuples()}
    gen = np.random.default_rng(seed + 1)  # separate stream, other data stays unchanged
    ranked = outlets.sort_values(["traffic_multiplier", "outlet_id"])
    ids = [int(i) for i in ranked["outlet_id"]]
    n_small = min(int(spec.get("small_outlets", 0)), max(len(ids) - 1, 0))
    small = gen.uniform(spec["small_min"], spec["small_max"], size=n_small)
    rest = np.sort(gen.uniform(spec["min"], spec["max"], size=len(ids) - n_small))
    levels = np.concatenate([np.sort(small), rest])
    return {i: round(float(v), 1) for i, v in zip(ids, levels)}


def average_calendar_factor(demand, start, end):
    """Mean of weekend and calendar effects over the whole period (so the level stays honest)."""
    days = pd.date_range(start, end)
    total = 0.0
    for d in days:
        f = calendar_factor(demand, d, start)
        if d.weekday() >= 5:
            f *= demand["weekend_multiplier"]
        total += f
    return total / len(days)


def daily_order_count(rng, demand, base, date, start, scale=1.0):
    expected = base / scale
    if date.weekday() >= 5:  # Saturday or Sunday
        expected *= demand["weekend_multiplier"]
    expected *= calendar_factor(demand, date, start)
    expected *= rng.lognormal(mean=0.0, sigma=demand["noise_sd"])
    n = int(rng.poisson(expected))
    floor = demand.get("outlet_orders", {}).get("floor", 0)
    return max(n, int(floor))


def main():
    cfg = load_config()
    demand = cfg["demand"]
    rng = np.random.default_rng(cfg["seed"])

    outlets = pd.read_csv(RAW_DIR / "outlets.csv")
    menu = pd.read_csv(RAW_DIR / "menu_items.csv")
    menu_id = dict(zip(menu["menu_name"], menu["menu_id"]))
    menu_price = dict(zip(menu["menu_id"], menu["price"]))

    mix_names, mix_p = normalize(demand["menu_mix"])
    mix_ids = [menu_id[name] for name in mix_names]
    hours, hour_p = normalize(demand["hourly_share"])
    sizes, size_p = normalize(demand["portions_per_order"])

    orders, items = [], []
    order_id = 1
    start = pd.Timestamp(cfg["start_date"])
    base_orders = outlet_base_orders(demand, outlets, cfg["seed"])
    scale = 1.0
    if demand.get("outlet_orders"):
        scale = average_calendar_factor(demand, start, cfg["end_date"])
    for _, outlet in outlets.iterrows():
        for date in pd.date_range(start, cfg["end_date"]):
            n = daily_order_count(rng, demand, base_orders[int(outlet["outlet_id"])], date, start, scale)
            order_hours = rng.choice(hours, size=n, p=hour_p)
            order_sizes = rng.choice(sizes, size=n, p=size_p)
            for hour, size in zip(order_hours, order_sizes):
                order_ts = date + pd.Timedelta(
                    hours=int(hour),
                    minutes=int(rng.integers(0, 60)),
                    seconds=int(rng.integers(0, 60)),
                )
                orders.append({
                    "order_id": order_id,
                    "outlet_id": int(outlet["outlet_id"]),
                    "order_ts": order_ts,
                })
                picked = rng.choice(mix_ids, size=int(size), p=mix_p)
                for mid, qty in zip(*np.unique(picked, return_counts=True)):
                    items.append({
                        "order_id": order_id,
                        "menu_id": int(mid),
                        "quantity": int(qty),
                        "unit_price": menu_price[int(mid)],
                    })
                order_id += 1

    # Number orders in time order so order_id follows the clock
    orders_df = pd.DataFrame(orders).sort_values("order_ts").reset_index(drop=True)
    new_id = dict(zip(orders_df["order_id"], range(1, len(orders_df) + 1)))
    orders_df["order_id"] = orders_df["order_id"].map(new_id)
    items_df = pd.DataFrame(items)
    items_df["order_id"] = items_df["order_id"].map(new_id)
    items_df = items_df.sort_values(["order_id", "menu_id"]).reset_index(drop=True)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    orders_df.to_csv(RAW_DIR / "orders.csv", index=False)
    items_df.to_csv(RAW_DIR / "order_items.csv", index=False)
    per_day = orders_df.groupby("outlet_id").size() / (pd.Timestamp(cfg["end_date"]) - start).days
    print("average orders per day by outlet:", per_day.round(1).to_dict())
    print(f"orders: {len(orders_df)} rows")
    print(f"order_items: {len(items_df)} rows")


if __name__ == "__main__":
    main()
