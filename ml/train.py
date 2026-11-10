"""Train the demand forecast, compare it with the kitchen's routine and simulate the savings.

Run from the project root:
    python ml/train.py

Outputs (small files, committed so the online dashboard can show them):
    dashboard/sample_data/ml_predictions.csv.gz
    dashboard/sample_data/ml_summary.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

import data
import evaluate
import features

SEED = 42
VAL_START = "2025-09-01"   # train: before this date
TEST_START = "2025-11-01"  # validation: Sep-Oct (tune the safety factor), test: Nov-Dec
KITCHEN_SAFETY = 1.05      # the kitchen's current rule: cook 5% above its own forecast
OUT_DIR = data.SAMPLE_DIR


def make_model():
    return HistGradientBoostingRegressor(
        loss="poisson",              # sales are counts, so a count-friendly loss fits well
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=15,
        min_samples_leaf=40,
        l2_regularization=1.0,
        categorical_features="from_dtype",
        random_state=SEED,
    )


def fit(frame):
    """Learn sales relative to the typical level of each outlet and menu (scale-free)."""
    model = make_model()
    model.fit(frame[features.FEATURES], frame["portions"] / frame["level"])
    return model


def predict(model, frame):
    return model.predict(frame[features.FEATURES]) * frame["level"].to_numpy()


def round_floats(obj, digits=2):
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    return round(obj, digits) if isinstance(obj, float) else obj


def main(folder=None, out_dir=OUT_DIR):
    marts = data.load_marts(folder)
    sales, production = marts["mart_daily_sales"], marts["mart_daily_production"]
    df = features.build_dataset(sales, production, data.load_holidays())
    train, val, test = features.split_by_date(df, VAL_START, TEST_START)
    print(f"rows: train {len(train)}, validation {len(val)}, test {len(test)}")

    # 1) fit on train, check on validation, tune the safety factor
    model = fit(train)
    val_pred = predict(model, val)
    waste_cost, lost_profit = evaluate.unit_costs(sales, production)
    safety = evaluate.tune_safety(val, val_pred, waste_cost, lost_profit)
    names = dict(zip(df["menu_id"].astype(int), df["menu_name"]))
    print("safety factor chosen on validation:", {names[m]: v for m, v in safety.items()})

    # 2) refit on train + validation, then judge once on the untouched test period
    final = fit(pd.concat([train, val]))
    test_pred = predict(final, test)

    forecasts = {
        "Same day last week": test["lag_7"].to_numpy(),
        "Kitchen rule (14-day average)": test["portions_forecast"].to_numpy(),
        "ML model": test_pred,
    }
    accuracy = {name: evaluate.forecast_metrics(test["portions"], f) for name, f in forecasts.items()}

    plans = {
        "Kitchen today": test["portions_planned"].to_numpy(),
        "Kitchen rule, no human error": np.ceil(test["portions_forecast"] * KITCHEN_SAFETY),
        "ML model": evaluate.apply_safety(test, test_pred, safety),
    }
    money = {name: evaluate.simulate(test, plan, waste_cost, lost_profit) for name, plan in plans.items()}
    saving = money["Kitchen today"]["total_cost_idr"] - money["ML model"]["total_cost_idr"]
    saving_pct = saving / money["Kitchen today"]["total_cost_idr"] * 100

    # 3) which inputs matter most (measured on validation, with the train-only model)
    imp = permutation_importance(
        model, val[features.FEATURES], val["portions"] / val["level"],
        scoring="neg_mean_absolute_error", n_repeats=3, random_state=SEED,
    )
    importance = (
        pd.Series(imp.importances_mean, index=features.FEATURES)
        .sort_values(ascending=False).head(8)
    )

    summary = {
        "split": {"train_end": VAL_START, "test_start": TEST_START,
                  "test_days": int(test["date_day"].nunique()),
                  "test_end": str(test["date_day"].max().date())},
        "safety_factor": {names[m]: v for m, v in safety.items()},
        "accuracy": accuracy,
        "money": money,
        "saving_idr": saving,
        "saving_pct": saving_pct,
        "importance_pct": (importance.clip(lower=0) / importance.clip(lower=0).sum() * 100).to_dict(),
        "assumption": "Portions that were wanted but not cooked are treated as lost sales (lost profit).",
    }

    out = test[["date_day", "outlet_id", "outlet_name", "menu_name", "portions", "portions_forecast", "portions_planned"]].copy()
    out["last_week"] = test["lag_7"].to_numpy()
    out["model_forecast"] = test_pred
    out["model_plan"] = plans["ML model"]
    out["rule_plan"] = plans["Kitchen rule, no human error"]
    # money per portion, so the dashboard can redo the simulation for any filter
    menu_id = test["menu_id"].astype(int)
    out["waste_cost_per_portion"] = menu_id.map(waste_cost).astype(float).to_numpy()
    out["lost_profit_per_portion"] = menu_id.map(lost_profit).astype(float).to_numpy()
    out = out.rename(columns={"portions": "actual", "portions_forecast": "rule_forecast",
                              "portions_planned": "kitchen_plan"})
    out = out.round({"rule_forecast": 1, "model_forecast": 1, "last_week": 0,
                     "waste_cost_per_portion": 0, "lost_profit_per_portion": 0})

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "ml_predictions.csv.gz", index=False)
    (out_dir / "ml_summary.json").write_text(json.dumps(round_floats(summary), indent=2), encoding="utf-8")

    print("\nForecast error on the test period (lower is better)")
    for name, m in accuracy.items():
        print(f"  {name:32s} MAE {m['mae']:.2f} portions   WAPE {m['wape_pct']:.1f}%")
    print("\nMoney simulation on the test period (IDR)")
    for name, m in money.items():
        print(f"  {name:32s} waste {m['waste_cost_idr']:>12,.0f}   missed profit {m['lost_profit_idr']:>12,.0f}"
              f"   total {m['total_cost_idr']:>12,.0f}   service {m['service_level_pct']:.1f}%")
    print(f"\nSaving vs kitchen today: IDR {saving:,.0f} ({saving_pct:.1f}%)")
    print("Top inputs:", ", ".join(f"{k} ({v:.3f})" for k, v in importance.items()))
    return summary


if __name__ == "__main__":
    main()
