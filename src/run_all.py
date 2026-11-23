"""Rebuild everything from the raw download with one command.

    python -I src/run_all.py                  # full rebuild, then execute the notebook
    python -I src/run_all.py --skip-notebook  # everything except the notebook

Steps: download (skipped if the zip exists) -> ingest the Excel workbook to parquet
-> clean with pandas -> SQL with DuckDB -> key metrics -> charts -> Excel report
(+ openpyxl check) -> execute notebooks/customer_analytics.ipynb in place.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_excel  # noqa: E402
import charts  # noqa: E402
import clean  # noqa: E402
import config  # noqa: E402
import download  # noqa: E402
import ingest  # noqa: E402
import metrics  # noqa: E402
import run_sql  # noqa: E402


def execute_notebook() -> None:
    subprocess.run(
        [sys.executable, "-m", "nbconvert", "--to", "notebook", "--execute", "--inplace",
         "--ExecutePreprocessor.timeout=600", str(config.NOTEBOOK_PATH)],
        check=True, cwd=config.NOTEBOOK_PATH.parent)
    size_mb = config.NOTEBOOK_PATH.stat().st_size / 1e6
    print(f"  executed {config.NOTEBOOK_PATH.relative_to(config.ROOT)} ({size_mb:.1f} MB)")


def main() -> None:
    steps = [
        ("1/8 download raw data", download.ensure_raw),
        ("2/8 ingest Excel workbook -> parquet", ingest.ingest),
        ("3/8 clean transaction lines (pandas)", clean.clean),
        ("4/8 run SQL queries (DuckDB)", run_sql.run_sql),
        ("5/8 key metrics", metrics.compute),
        ("6/8 charts", charts.make_charts),
        ("7/8 Excel report", lambda: (build_excel.build(), build_excel.verify())),
    ]
    if "--skip-notebook" not in sys.argv:
        steps.append(("8/8 execute notebook", execute_notebook))
    config.RESULTS_DIR.mkdir(exist_ok=True)
    config.IMAGES_DIR.mkdir(exist_ok=True)
    started = time.time()
    for label, step in steps:
        print(f"[{label}]")
        t = time.time()
        step()
        print(f"  ({time.time() - t:.0f}s)")
    print(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
