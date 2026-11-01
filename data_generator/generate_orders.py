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


def daily_order_count(rng, demand, traffic, date):
    expected = demand["base_orders_per_day"] * traffic
    if date.weekday() >= 5:  # Saturday or Sunday
        expected *= demand["weekend_multiplier"]
    expected *= rng.lognormal(mean=0.0, sigma=demand["noise_sd"])
    return int(rng.poisson(expected))


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
    for _, outlet in outlets.iterrows():
        for date in pd.date_range(cfg["start_date"], cfg["end_date"]):
            n = daily_order_count(rng, demand, outlet["traffic_multiplier"], date)
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
    print(f"orders: {len(orders_df)} rows")
    print(f"order_items: {len(items_df)} rows")


if __name__ == "__main__":
    main()