"""Step 4 - run every query in sql/ with DuckDB against the cleaned parquet files.

Each file sql/NN_name.sql holds one SELECT. The runner executes the files in order,
saves each result to results/name.csv and keeps it as a DuckDB table called `name`,
so later queries can build on earlier ones (e.g. the segment summary reads the
customer-level RFM table).

Tables available to the queries:
  sales                 clean product sales lines (data/processed/sales_clean.parquet)
  cancellations         cancellation lines        (data/processed/cancellations.parquet)
  segment_definitions   segment order, rule and action text (src/segments.py)

Run:  python -I src/run_sql.py
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import segments  # noqa: E402


def sql_path(path: Path) -> str:
    """Quote a file path for use inside a DuckDB string literal."""
    return str(path).replace("'", "''")


def run_sql() -> None:
    config.RESULTS_DIR.mkdir(exist_ok=True)
    con = duckdb.connect()  # in-memory database
    con.execute(f"CREATE VIEW sales AS SELECT * FROM read_parquet('{sql_path(config.SALES_PARQUET)}')")
    con.execute("CREATE VIEW cancellations AS SELECT * FROM "
                f"read_parquet('{sql_path(config.CANCELLATIONS_PARQUET)}')")
    definitions = segments.definitions_frame()  # noqa: F841  (read by DuckDB by name)
    con.execute("CREATE TABLE segment_definitions AS SELECT * FROM definitions")

    for sql_file in sorted(config.SQL_DIR.glob("[0-9][0-9]_*.sql")):
        name = sql_file.stem.split("_", 1)[1]          # "04_rfm_customers" -> "rfm_customers"
        query = sql_file.read_text().strip().rstrip(";")
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {query}")
        result = con.execute(f"SELECT * FROM {name}").df()
        result.to_csv(config.RESULTS_DIR / f"{name}.csv", index=False)
        print(f"  {sql_file.name:<32} -> results/{name}.csv ({len(result):,} rows)")

    segments.verify(con.execute("SELECT * FROM rfm_customers").df())
    con.close()


if __name__ == "__main__":
    run_sql()
