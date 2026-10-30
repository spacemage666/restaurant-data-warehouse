"""Generate the dimension tables: outlets, ingredients, menu items, recipes"""
import random
from pathlib import Path
import pandas as pd
import yaml

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.parent / "data" / "raw"



def load_config():
    with open(BASE_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)

def make_outlets(cfg, rng):
    rows = []
    for i in range(1, cfg["n_outlets"] +1):
        loc_type = rng.choice(list(cfg["location_types"]))
        base = cfg["location_types"][loc_type]
        rows.append({
            "outlet_id": i,
            "outlet_name": f"Outlet {i:02d}",
            "city": rng.choice(cfg["cities"]),
            "location_type": loc_type,
            "traffic_multiplier": round(base * rng.uniform(0.85, 1.15),2),
        })
    return pd.DataFrame(rows)


def make_ingredients(cfg):
    rows = []
    for i, ing in enumerate(cfg["ingredients"], start=1):
        rows.append({
            "ingredient_id": i, **ing})
    return pd.DataFrame(rows)


def make_menu_and_recipes(cfg, ingredients):
    ing_id = dict(zip(ingredients["ingredient_name"], ingredients["ingredient_id"]))
    menu_rows, recipe_rows = [], []
    for i, item in enumerate(cfg["menu"], start=1):
        menu_rows.append({
            "menu_id": i,
            "menu_name": item["menu_name"],
            "category": item["category"],
            "price": item["price"],
        })
        for ing_name, qty in item["recipe"].items():
            recipe_rows.append({
                "menu_id": i,
                "ingredient_id": ing_id[ing_name],
                "qty_per_portion": qty,
            })
    return pd.DataFrame(menu_rows), pd.DataFrame(recipe_rows)


def main():
    cfg = load_config()
    rng = random.Random(cfg["seed"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    outlets = make_outlets(cfg, rng)
    ingredients = make_ingredients(cfg)
    menu_items, recipes = make_menu_and_recipes(cfg, ingredients)

    tables = {
        "outlets": outlets,
        "ingredients": ingredients,
        "menu_items": menu_items,
        "recipes": recipes,
    }
    for name, df in tables.items():
        df.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
        print(f"{name}: {len(df)} rows")



if __name__ == "__main__":
    main()