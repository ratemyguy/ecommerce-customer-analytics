"""Shared paths and constants for the e-commerce customer analytics project.

Every script in src/ imports this module, so a path or constant is defined
exactly once.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
RAW_DIR = ROOT / "data" / "raw" / "uci_online_retail_ii"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"
IMAGES_DIR = ROOT / "images"
NOTEBOOK_PATH = ROOT / "notebooks" / "customer_analytics.ipynb"

# ---------------------------------------------------------------- source data
# UCI Machine Learning Repository, "Online Retail II" (dataset 502), CC BY 4.0.
DATA_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
ZIP_PATH = RAW_DIR / "online_retail_ii.zip"
XLSX_NAME = "online_retail_II.xlsx"
XLSX_PATH = RAW_DIR / XLSX_NAME
# SHA-256 of the files as downloaded on 2026-11-23. A mismatch is reported
# (the source may have been re-published) but does not stop the pipeline.
ZIP_SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"
XLSX_SHA256 = "bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980"

# The workbook's sheets and header row, checked on read (never assumed).
EXPECTED_SHEETS = ["Year 2009-2010", "Year 2010-2011"]
EXPECTED_HEADER = [
    "Invoice", "StockCode", "Description", "Quantity",
    "InvoiceDate", "Price", "Customer ID", "Country",
]
# Snake-case names used from the parquet cache onwards.
COLUMN_NAMES = [
    "invoice", "stock_code", "description", "quantity",
    "invoice_date", "price", "customer_id", "country",
]

# ---------------------------------------------------------------- processed files
RAW_PARQUET = PROCESSED_DIR / "online_retail_ii_raw.parquet"
SALES_PARQUET = PROCESSED_DIR / "sales_clean.parquet"
CANCELLATIONS_PARQUET = PROCESSED_DIR / "cancellations.parquet"

# ---------------------------------------------------------------- chart style
# Portfolio palette: navy, teal, yellow, orange, gray (the charts use navy and gray;
# the Excel colour scale uses teal).
NAVY, TEAL, YELLOW, ORANGE, GRAY = "#1F3A5F", "#2A9D8F", "#E9C46A", "#E76F51", "#8D99AE"
SOURCE_NOTE = "Source: UCI Machine Learning Repository, Online Retail II (CC BY 4.0)"
