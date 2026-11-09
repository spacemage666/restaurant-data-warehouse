"""Export the gold marts to compressed CSV files (.csv.gz) so the dashboard can run without a database.

Run from the project root (with the database running):
    python dashboard/export_marts.py
"""
from dashboard_lib import SAMPLE_DIR, load_from_db


def main():
    SAMPLE_DIR.mkdir(exist_ok=True)
    for name, df in load_from_db().items():
        df.to_csv(SAMPLE_DIR / f"{name}.csv.gz", index=False)
        print(f"{name}: {len(df)} rows")
    print(f"Saved to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
