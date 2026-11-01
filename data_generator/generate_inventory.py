"""Plan daily production, restock ingredients and log food waste for every outlet."""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR.parent / "data" / "raw"
NEVER = pd.Timestamp("2262-01-01")  # "expiry date" of items that do not expire
EPS = 1e-9
NOT_FOOD = ("packaging", "utility")


def load_config():
    with open(BASE_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def portions_sold(orders, items, dates):
    """Portions sold per outlet, menu item and day."""
    orders = orders.assign(order_date=orders["order_ts"].dt.normalize())
    sold = items.merge(orders[["order_id", "outlet_id", "order_date"]], on="order_id")
    sold = sold.groupby(["outlet_id", "menu_id", "order_date"])["quantity"].sum()
    return sold.unstack("order_date").reindex(columns=dates).fillna(0.0)


def plan_production(sold, dates, prod):
    """The kitchen cooks forecast x safety factor; it cooks more if it sells out."""
    weekend = np.asarray(dates.day_of_week >= 5)
    window = prod["forecast_window_days"]
    plans, rows = {}, []
    for (outlet_id, menu_id), series in sold.iterrows():
        sold_arr = series.to_numpy()
        planned = np.zeros(len(dates))
        forecast = np.zeros(len(dates))
        for t in range(len(dates)):
            same_type = [sold_arr[k] for k in range(max(0, t - window), t)
                         if weekend[k] == weekend[t]]
            if len(same_type) < 2:  # warm-up: use the first week
                same_type = [sold_arr[k] for k in range(min(7, len(dates)))
                             if weekend[k] == weekend[t]] or list(sold_arr[:7])
            forecast[t] = sum(same_type) / len(same_type)
            planned[t] = math.ceil(forecast[t] * prod["safety_factor"])
        cooked = np.maximum(planned, sold_arr)
        plans[(int(outlet_id), int(menu_id))] = (sold_arr, planned, cooked)
        for t, date in enumerate(dates):
            rows.append({
                "outlet_id": int(outlet_id), "menu_id": int(menu_id),
                "production_date": date, "portions_forecast": round(forecast[t], 1),
                "portions_planned": int(planned[t]), "portions_sold": int(sold_arr[t]),
                "portions_cooked": int(cooked[t]),
                "portions_wasted": int(max(0, planned[t] - sold_arr[t])),
            })
    return plans, pd.DataFrame(rows)


def ingredient_usage(plans, recipe_by_menu, category):
    """Ingredient usage per outlet and day. Packaging follows sales, food follows cooking."""
    usage = {}
    for (outlet_id, menu_id), (sold_arr, _, cooked) in plans.items():
        for ing_id, qty in recipe_by_menu[menu_id]:
            amount = sold_arr if category[ing_id] == "packaging" else cooked
            usage[(outlet_id, ing_id)] = usage.get((outlet_id, ing_id), 0.0) + amount * qty
    return usage


def overproduction_waste(plans, recipe_by_menu, category, dates):
    """Ingredients thrown away inside the cooked portions that were not sold."""
    acc = {}
    for (outlet_id, menu_id), (sold_arr, planned, _) in plans.items():
        wasted = np.maximum(planned - sold_arr, 0)
        for ing_id, qty in recipe_by_menu[menu_id]:
            if category[ing_id] in NOT_FOOD:
                continue
            acc[(outlet_id, ing_id)] = acc.get((outlet_id, ing_id), 0.0) + wasted * qty
    rows = []
    for (outlet_id, ing_id), arr in acc.items():
        for t in np.nonzero(arr > EPS)[0]:
            rows.append({"outlet_id": outlet_id, "ingredient_id": ing_id,
                         "waste_date": dates[t], "reason": "overproduction",
                         "quantity": round(float(arr[t]), 2)})
    return rows


def forecast(demand, t, window):
    """Average usage of the last `window` days (first days use the first week)."""
    past = demand[max(0, t - window):t]
    if len(past) == 0:
        past = demand[:window]
    return float(past.mean())


def take(lots, qty):
    """Use stock from the lots that expire first. Returns what could not be covered."""
    for lot in sorted(lots, key=lambda lot: lot["expires"]):
        used = min(lot["qty"], qty)
        lot["qty"] -= used
        qty -= used
        if qty <= EPS:
            return 0.0
    return qty


def total(lots):
    return sum(lot["qty"] for lot in lots)


def round_qty(qty, unit):
    return math.ceil(qty) if unit == "pcs" else round(qty, 1)


def simulate(outlet_id, ing, demand, dates, inv):
    """Day-by-day stock simulation for one ingredient at one outlet."""
    storage = ing["storage"] if isinstance(ing["storage"], str) else "unspecified"
    cycle = inv["restock_cycle_days"][storage]
    offset = outlet_id % cycle  # outlets are restocked on different weekdays
    shelf = ing["shelf_life_days"]
    frozen = storage == "frozen"
    stock, thawed = [], []  # frozen items: stock = freezer, thawed = ready to use
    purchases, waste = [], []

    def expiry(date, days):
        return NEVER if pd.isna(days) else date + pd.Timedelta(days=int(days))

    def buy(date, qty, kind, keep):
        qty = round_qty(qty, ing["unit"])
        purchases.append({"outlet_id": outlet_id, "ingredient_id": ing["ingredient_id"],
                          "purchase_date": date, "purchase_type": kind,
                          "quantity": qty, "unit_price": ing["price_per_unit"]})
        if keep:
            stock.append({"qty": qty, "expires": expiry(date, shelf)})

    for t, date in enumerate(dates):
        # 1. throw away anything that expired
        for lots, reason in ((stock, "expired_frozen" if frozen else "expired"),
                             (thawed, "expired_after_thaw")):
            for lot in lots:
                if lot["qty"] > EPS and lot["expires"] <= date:
                    waste.append({"outlet_id": outlet_id, "ingredient_id": ing["ingredient_id"],
                                  "waste_date": date, "reason": reason,
                                  "quantity": round(lot["qty"], 2)})
                    lot["qty"] = 0.0
            lots[:] = [lot for lot in lots if lot["qty"] > EPS]

        fc = forecast(demand, t, inv["forecast_window_days"])

        # 2. scheduled restock: top up to the forecast for the next cycle
        if t == 0 or t % cycle == offset:
            need = fc * (cycle + 1) * inv["safety_factor"] - total(stock) - total(thawed)
            if need > EPS:
                buy(date, need, "scheduled", keep=True)

        # 3. frozen items: thaw the forecast amount for today
        if frozen:
            planned = fc * inv["safety_factor"] - total(thawed)
            if planned > EPS:
                moved = planned - take(stock, planned)
                if moved > EPS:
                    thawed.append({"qty": moved,
                                   "expires": expiry(date, ing["thawed_shelf_life_days"])})

        # 4. serve today's usage (first from thawed stock, then straight from the freezer)
        short = take(thawed if frozen else stock, demand[t])
        if short > EPS and frozen:
            short = take(stock, short)
        if short > EPS:
            buy(date, short, "emergency", keep=False)  # ran out: buy and use immediately
    return purchases, waste


def main():
    cfg = load_config()
    dates = pd.date_range(cfg["start_date"], cfg["end_date"])
    orders = pd.read_csv(RAW_DIR / "orders.csv", parse_dates=["order_ts"])
    items = pd.read_csv(RAW_DIR / "order_items.csv")
    recipes = pd.read_csv(RAW_DIR / "recipes.csv")
    ingredients = pd.read_csv(RAW_DIR / "ingredients.csv").set_index("ingredient_id", drop=False)
    category = ingredients["category"].to_dict()
    recipe_by_menu = {
        int(menu_id): list(zip(group["ingredient_id"].astype(int), group["qty_per_portion"]))
        for menu_id, group in recipes.groupby("menu_id")
    }

    sold = portions_sold(orders, items, dates)
    plans, production_df = plan_production(sold, dates, cfg["production"])
    usage = ingredient_usage(plans, recipe_by_menu, category)

    all_purchases = []
    all_waste = overproduction_waste(plans, recipe_by_menu, category, dates)
    for (outlet_id, ingredient_id), demand in usage.items():
        ing = ingredients.loc[ingredient_id].to_dict()
        purchases, waste = simulate(outlet_id, ing, demand, dates, cfg["inventory"])
        all_purchases += purchases
        all_waste += waste

    purchases_df = pd.DataFrame(all_purchases).sort_values(
        ["purchase_date", "outlet_id", "ingredient_id"]).reset_index(drop=True)
    purchases_df.insert(0, "purchase_id", range(1, len(purchases_df) + 1))
    waste_df = pd.DataFrame(all_waste).sort_values(
        ["waste_date", "outlet_id", "ingredient_id", "reason"]).reset_index(drop=True)
    waste_df.insert(0, "waste_id", range(1, len(waste_df) + 1))

    production_df.to_csv(RAW_DIR / "production_logs.csv", index=False)
    purchases_df.to_csv(RAW_DIR / "purchases.csv", index=False)
    waste_df.to_csv(RAW_DIR / "waste_logs.csv", index=False)
    print(f"production_logs: {len(production_df)} rows")
    print(f"purchases: {len(purchases_df)} rows")
    print(f"waste_logs: {len(waste_df)} rows")


if __name__ == "__main__":
    main()