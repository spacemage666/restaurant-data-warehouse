"""Run the whole pipeline with one command, from an empty database to the dashboard data.

    python run_pipeline.py                 # every step
    python run_pipeline.py --skip generate # reuse the CSV files already in data/raw
    python run_pipeline.py --only dbt      # only one step (or several)
    python run_pipeline.py --dry-run       # show what would run, change nothing

Steps, in order:
    database        start PostgreSQL (Docker) and wait until it accepts connections
    generate        synthetic dimensions, orders and inventory CSV files
    bronze          load the CSV files into the bronze schema
    dbt             build silver and gold models and run all data tests
    dashboard-data  export the gold marts as small files for the dashboard
    forecast        train the demand model and write its predictions
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
STEP_NAMES = ["database", "generate", "bronze", "dbt", "dashboard-data", "forecast"]


def dbt_command():
    """Use the dbt that lives next to this Python (the virtual environment)."""
    local = Path(PYTHON).parent / "dbt"
    return str(local) if local.exists() else (shutil.which("dbt") or "dbt")


def build_steps():
    """Each step is a list of (command, working folder)."""
    return {
        "database": [(["docker", "compose", "up", "-d"], ROOT)],
        "generate": [
            ([PYTHON, "data_generator/generate_dimensions.py"], ROOT),
            ([PYTHON, "data_generator/generate_orders.py"], ROOT),
            ([PYTHON, "data_generator/generate_inventory.py"], ROOT),
        ],
        "bronze": [([PYTHON, "ingestion/load_bronze.py"], ROOT)],
        "dbt": [([dbt_command(), "build"], ROOT / "dbt_project")],
        "dashboard-data": [([PYTHON, "dashboard/export_marts.py"], ROOT)],
        "forecast": [([PYTHON, "ml/train.py"], ROOT)],
    }


def wait_for_database(env, timeout=90):
    """Wait until PostgreSQL accepts connections (the container needs a few seconds)."""
    import psycopg

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with psycopg.connect(
                host=env.get("POSTGRES_HOST", "localhost"),
                port=env.get("POSTGRES_PORT", "5433"),
                dbname=env["POSTGRES_DB"],
                user=env["POSTGRES_USER"],
                password=env["POSTGRES_PASSWORD"],
                connect_timeout=3,
            ):
                return True
        except Exception:
            time.sleep(2)
    return False


def main():
    parser = argparse.ArgumentParser(description="Run the restaurant data warehouse pipeline.")
    parser.add_argument("--only", nargs="+", choices=STEP_NAMES, help="run only these steps")
    parser.add_argument("--skip", nargs="+", choices=STEP_NAMES, default=[], help="skip these steps")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = parser.parse_args()

    selected = [s for s in STEP_NAMES if (args.only is None or s in args.only) and s not in args.skip]
    if not selected:
        sys.exit("Nothing to run.")

    env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}
    needs_database = any(s in selected for s in ("database", "bronze", "dbt", "dashboard-data"))
    if needs_database and "POSTGRES_PASSWORD" not in env and not args.dry_run:
        sys.exit("POSTGRES_PASSWORD not found. Create .env from .env.example first.")

    steps = build_steps()
    timings = []
    start_all = time.time()
    for name in selected:
        print(f"\n=== {name} ===", flush=True)
        t0 = time.time()
        for command, folder in steps[name]:
            print("$", " ".join(command), flush=True)
            if args.dry_run:
                continue
            result = subprocess.run(command, cwd=folder, env=env)
            if result.returncode != 0:
                sys.exit(f"\nStep '{name}' failed (exit code {result.returncode}). Fix it, then rerun.")
        if name == "database" and not args.dry_run:
            print("waiting for PostgreSQL ...", flush=True)
            if not wait_for_database(env):
                sys.exit("PostgreSQL did not become ready in time. Check: docker compose ps")
        timings.append((name, time.time() - t0))

    print("\n=== done ===")
    for name, seconds in timings:
        print(f"  {name:15s} {seconds:6.1f} s")
    print(f"  {'total':15s} {time.time() - start_all:6.1f} s")


if __name__ == "__main__":
    main()
