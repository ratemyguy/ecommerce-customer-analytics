"""Step 2 - read the raw Excel workbook once and cache it as parquet.

The UCI workbook holds ~1.07M transaction lines in two sheets. Reading it
with openpyxl takes a few minutes, so this step streams the rows (read-only
mode, constant memory) into one typed parquet file. Every later step reads
the parquet, never the workbook.

Nothing is cleaned here: values are only typed. Excel stores some invoice
numbers and stock codes as numbers and others as text, so both columns are
stored as text. Two traceability columns are added: the source sheet and the
Excel row number.

Run:  python -I src/ingest.py
"""
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

BATCH_ROWS = 100_000

SCHEMA = pa.schema([
    ("invoice", pa.string()),
    ("stock_code", pa.string()),
    ("description", pa.string()),
    ("quantity", pa.int64()),
    ("invoice_date", pa.timestamp("s")),
    ("price", pa.float64()),
    ("customer_id", pa.int64()),
    ("country", pa.string()),
    ("sheet", pa.string()),
    ("sheet_row", pa.int32()),
])


def as_text(value):
    """Invoice / StockCode / Description / Country: Excel mixes numbers and text."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def as_int(value):
    """Quantity and Customer ID are whole numbers; refuse anything else."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"unexpected boolean {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise TypeError(f"expected a whole number, got {value!r}")


def as_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise TypeError(f"expected a number, got {value!r}")


def as_datetime(value):
    if not isinstance(value, datetime):
        raise TypeError(f"expected a datetime, got {value!r}")
    return value


CONVERTERS = [as_text, as_text, as_text, as_int, as_datetime, as_float, as_int, as_text]


def ingest(xlsx_path: Path = config.XLSX_PATH, out_path: Path = config.RAW_PARQUET) -> None:
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = load_workbook(xlsx_path, read_only=True, data_only=True)
    if workbook.sheetnames != config.EXPECTED_SHEETS:
        raise ValueError(f"unexpected sheets {workbook.sheetnames}")

    # A census of the Python types openpyxl returns per column, printed at the
    # end so a surprise (e.g. a quantity stored as text) is visible.
    type_census = {name: Counter() for name in config.COLUMN_NAMES}
    tmp_path = out_path.with_suffix(".tmp")
    writer = pq.ParquetWriter(tmp_path, SCHEMA, compression="zstd")
    total = 0
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            header = list(next(rows))
            if header != config.EXPECTED_HEADER:
                raise ValueError(f"sheet {sheet.title!r}: unexpected header {header}")
            columns = {name: [] for name in SCHEMA.names}
            sheet_lines = 0
            for excel_row, values in enumerate(rows, start=2):
                if all(v is None for v in values):
                    continue  # trailing empty rows, if any
                for name, convert, value in zip(config.COLUMN_NAMES, CONVERTERS, values):
                    type_census[name][type(value).__name__] += 1
                    try:
                        columns[name].append(convert(value))
                    except TypeError as err:
                        raise TypeError(f"{sheet.title!r} row {excel_row}, {name}: {err}") from err
                columns["sheet"].append(sheet.title)
                columns["sheet_row"].append(excel_row)
                sheet_lines += 1
                if len(columns["invoice"]) >= BATCH_ROWS:
                    writer.write_table(pa.table(columns, schema=SCHEMA))
                    columns = {name: [] for name in SCHEMA.names}
            if columns["invoice"]:
                writer.write_table(pa.table(columns, schema=SCHEMA))
            total += sheet_lines
            print(f"  {sheet.title}: {sheet_lines:,} lines")
    finally:
        writer.close()
        workbook.close()
    tmp_path.replace(out_path)

    print("  Python types read per column:")
    for name, census in type_census.items():
        print(f"    {name:<13} {dict(census)}")
    size_mb = out_path.stat().st_size / 1e6
    print(f"  wrote {total:,} lines to {out_path.relative_to(config.ROOT)} "
          f"({size_mb:.1f} MB) in {time.time() - started:.0f}s")


if __name__ == "__main__":
    ingest()
