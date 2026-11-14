"""Smoke test: start the Streamlit dashboard without a browser and check that it really draws something.

Run from the project root:
    python ci/dashboard_smoke_test.py

It fails (exit code 1) when the app raises an error or shows an empty page,
for example if dashboard/app.py is accidentally emptied.
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
app = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=180).run()

problems = []
if app.exception:
    problems.append("the app raised: " + "; ".join(str(e.value) for e in app.exception))
if len(app.tabs) < 4:
    problems.append(f"expected at least 4 tabs, found {len(app.tabs)}")
if len(app.metric) + len(app.markdown) == 0:
    problems.append("the page has no content")

if problems:
    print("Dashboard smoke test FAILED:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print(f"Dashboard smoke test passed: {len(app.tabs)} tabs, {len(app.metric)} metrics, {len(app.markdown)} text blocks.")
