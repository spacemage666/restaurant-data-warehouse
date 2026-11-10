"""Forecast accuracy and the money simulation (waste vs missed sales)."""
import numpy as np
import pandas as pd


def forecast_metrics(actual, forecast):
    """MAE in portions, RMSE, and WAPE (total absolute error / total sales)."""
    err = np.asarray(actual, dtype=float) - np.asarray(forecast, dtype=float)
    return {
        "mae": float(np.abs(err).mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "wape_pct": float(np.abs(err).sum() / np.sum(actual) * 100),
    }


def unit_costs(sales, production):
    """Money per portion for each menu item, taken from the gold marts.

    waste_cost: ingredient cost of one portion that is cooked and thrown away.
    lost_profit: profit we miss when a customer wants a portion that was not cooked.
    """
    waste = production.groupby("menu_id")[["wasted_food_cost", "portions_wasted"]].sum()
    waste_cost = waste["wasted_food_cost"] / waste["portions_wasted"].clip(lower=1)
    profit = sales.groupby("menu_id")[["gross_profit", "portions"]].sum()
    lost_profit = profit["gross_profit"] / profit["portions"].clip(lower=1)
    return waste_cost, lost_profit


def simulate(frame, plan, waste_cost, lost_profit):
    """Compare a cooking plan with what was actually sold (one row per outlet, menu, day).

    Assumption: portions that were not cooked but were wanted are lost sales.
    """
    sold = frame["portions"].to_numpy()
    plan = np.asarray(plan, dtype=float)
    wasted = np.maximum(plan - sold, 0.0)
    unmet = np.maximum(sold - plan, 0.0)
    waste_idr = float((wasted * frame["menu_id"].map(waste_cost).astype(float).to_numpy()).sum())
    lost_idr = float((unmet * frame["menu_id"].map(lost_profit).astype(float).to_numpy()).sum())
    return {
        "portions_cooked": float(plan.sum()),
        "portions_wasted": float(wasted.sum()),
        "portions_unmet": float(unmet.sum()),
        "waste_rate_pct": float(wasted.sum() / plan.sum() * 100),
        "service_level_pct": float((1 - unmet.sum() / sold.sum()) * 100),
        "waste_cost_idr": waste_idr,
        "lost_profit_idr": lost_idr,
        "total_cost_idr": waste_idr + lost_idr,
    }


def tune_safety(frame, forecast, waste_cost, lost_profit, grid=None):
    """Pick, for each menu item, the safety factor (cook this much above the forecast)
    with the lowest total cost. Returns {menu_id: factor}.

    A menu with expensive ingredients and a small profit should be cooked closer to the
    forecast than a cheap one, so every menu item gets its own factor.
    """
    grid = np.round(np.arange(0.80, 1.41, 0.01), 2) if grid is None else grid
    menu_ids = frame["menu_id"].astype(int).to_numpy()
    best = {}
    for menu_id in sorted(set(menu_ids)):
        mask = menu_ids == menu_id
        part, fc = frame[mask], np.asarray(forecast)[mask]
        costs = [simulate(part, np.ceil(fc * s), waste_cost, lost_profit)["total_cost_idr"] for s in grid]
        best[int(menu_id)] = float(grid[int(np.argmin(costs))])
        if best[int(menu_id)] in (grid[0], grid[-1]):
            print(f"  warning: menu {menu_id} hit the edge of the search range, widen the grid")
    return best


def apply_safety(frame, forecast, safety_by_menu):
    """Cooking plan = forecast x the safety factor of that menu item, rounded up."""
    factor = frame["menu_id"].astype(int).map(safety_by_menu).to_numpy()
    return np.ceil(np.asarray(forecast) * factor)
