"""Step 3 - clean the transaction lines with pandas.

Input : data/processed/online_retail_ii_raw.parquet  (from ingest.py)
Output: data/processed/sales_clean.parquet     product sales lines
        data/processed/cancellations.parquet   cancellation lines, kept for the cancellation metric
        results/data_quality.csv               one row per cleaning rule (a waterfall)
        results/non_product_codes.csv          every non-standard stock code and what was done with it
        results/voided_sales_lines.csv         every sale line removed as a same-day void (rule 6)

Rules, applied in this order (each line is counted under the first rule that catches it):
  1-2. Drop exact duplicate lines. The two sheets overlap: 1-9 Dec 2010 appears in both.
  3.   Set aside cancellations (Invoice starting with "C") for the cancellation-rate metric.
  4.   Drop non-cancellation lines with quantity <= 0 or price <= 0 (stock write-offs,
       zero-price lines, bad-debt adjustments).
  5.   Drop non-product stock codes (postage, carriage, manual adjustments, discounts,
       samples, bank charges, Amazon fees, vouchers, test items) - found by inspecting
       every stock code that does not look like a product code, plus descriptions.
  6.   Drop sale lines voided within 24 hours by the same customer: by an identical
       cancellation line (same stock code, unit price and quantity) or by a manual credit
       for exactly the line's value. These are keying errors, not sales: the two largest
       lines in the whole file (80,995 and 74,215 units) were cancelled 12 and 16 minutes
       after they were entered. Their cancellation lines are flagged so the cancellation
       rate excludes them too.
  Kept but flagged: lines with no Customer ID count towards revenue totals and are
  excluded from customer-level analysis (cohorts, RFM, segments).

Run:  python -I src/clean.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

# Stock codes that are not merchandise, with the reason. Codes are compared after
# upper-casing and trimming (the file has "m" next to "M", and "47503J " with a space).
NON_PRODUCT_CODES = {
    "POST": "Postage charge",
    "DOT": "Dotcom (web order) postage charge",
    "C2": "Carriage charge",
    "C3": "Carriage-style code with no description",
    "23444": "Next Day Carriage (delivery fee on a product-style code)",
    "23574": "Packing charge (fee on a product-style code)",
    "M": "Manual adjustment",
    "D": "Discount",
    "S": "Samples",
    "BANK CHARGES": "Bank charges",
    "ADJUST": "Manual stock/price adjustment",
    "ADJUST2": "Manual stock/price adjustment",
    "B": "Adjust bad debt",
    "AMAZONFEE": "Amazon marketplace fee",
    "CRUK": "CRUK (charity) commission",
    "TEST001": "Test product",
    "TEST002": "Test product",
    "PADS": "Placeholder line priced at 0.001 GBP",
    "GIFT": "Gift code with no description",
    "22016": "Gift voucher on a product-style code",
    "23702": "High-resolution image (not merchandise)",
}
VOUCHER_PATTERN = re.compile(r"^GIFT_0001_\d+$")   # Dotcomgiftshop gift vouchers
PRODUCT_PATTERN = re.compile(r"^\d{5}[A-Z]{0,2}$")  # e.g. 85123A, 15056BL, 22423
VOID_WINDOW = pd.Timedelta(hours=24)


def non_product_reason(code: str):
    """Return why a (normalised) stock code is not a product, or None if it is one."""
    if code in NON_PRODUCT_CODES:
        return NON_PRODUCT_CODES[code]
    if VOUCHER_PATTERN.match(code):
        return "Gift voucher"
    return None


def match_same_day_voids(sales: pd.DataFrame, cancels: pd.DataFrame) -> tuple[dict, int]:
    """Pair sale lines with the cancellation that voided them within 24 hours.

    Pass 1 - identical line: same customer, stock code, unit price and quantity
    (cancellation quantity = -sale quantity), cancelled 0-24 h after the sale.
    Pairing is one-to-one: earliest cancellation first, each takes its latest unused sale.
    Pass 2 - manual credit: a "Manual" cancellation (code M, quantity -1) whose amount
    equals the value of exactly one remaining sale line of the same customer in the
    previous 24 h (e.g. 60 picnic sets keyed at 649.50 each, credited 3 minutes later
    and re-keyed as one set). Ambiguous credits (several candidate lines) are left alone.
    Lines with no Customer ID are never paired.
    Returns ({sale row label: cancellation row label}, number paired in pass 2).
    """
    def within_window(pairs):
        gap = pairs["invoice_date_c"] - pairs["invoice_date_s"]
        return pairs[(gap >= pd.Timedelta(0)) & (gap <= VOID_WINDOW)]

    known_sales = sales[sales["customer_id"].notna()]
    known_cancels = cancels[cancels["customer_id"].notna() & (cancels["quantity"] < 0)]

    # ---- pass 1: identical lines (product cancellations only)
    keys = ["customer_id", "stock_code", "price", "quantity"]
    c = known_cancels.loc[known_cancels["is_product"], keys + ["invoice_date"]].copy()
    c["quantity"] = -c["quantity"]
    pairs = within_window(c.reset_index(names="c_row").merge(
        known_sales[keys + ["invoice_date"]].reset_index(names="s_row"),
        on=keys, suffixes=("_c", "_s")))
    pairs = pairs.sort_values(["invoice_date_c", "c_row", "invoice_date_s"],
                              ascending=[True, True, False])
    paired = {}                       # sale row -> cancellation row
    used_cancels = set()
    for c_row, s_row in zip(pairs["c_row"], pairs["s_row"]):
        if c_row in used_cancels or s_row in paired:
            continue
        used_cancels.add(c_row)
        paired[s_row] = c_row

    # ---- pass 2: a manual credit for exactly one line's value
    m = known_cancels[(known_cancels["stock_code"] == "M") & (known_cancels["quantity"] == -1)]
    m = m.assign(amount=m["price"].round(2))[["customer_id", "amount", "invoice_date"]]
    rest = known_sales[~known_sales.index.isin(list(paired))]
    rest = rest.assign(amount=rest["line_value"].round(2))[["customer_id", "amount", "invoice_date"]]
    pairs = within_window(m.reset_index(names="c_row").merge(
        rest.reset_index(names="s_row"), on=["customer_id", "amount"], suffixes=("_c", "_s")))
    unique = pairs.groupby("c_row")["s_row"].transform("size") == 1
    n_manual = 0
    for c_row, s_row in zip(pairs.loc[unique, "c_row"], pairs.loc[unique, "s_row"]):
        if s_row not in paired:
            paired[s_row] = c_row
            n_manual += 1
    return paired, n_manual


def clean() -> None:
    raw = pd.read_parquet(config.RAW_PARQUET)
    # pandas reads an integer column with nulls as float; keep IDs as nullable integers.
    raw["customer_id"] = raw["customer_id"].astype("Int64")
    # Keep the workbook's own order (sheet 1 first) so "first copy" is well defined.
    raw["sheet"] = pd.Categorical(raw["sheet"], categories=config.EXPECTED_SHEETS, ordered=True)
    raw = raw.sort_values(["sheet", "sheet_row"], ignore_index=True)
    raw["line_value"] = raw["quantity"] * raw["price"]
    n_raw = len(raw)
    log = []  # rows of results/data_quality.csv

    def record(rule, action, mask_or_frame, note=""):
        frame = raw[mask_or_frame] if isinstance(mask_or_frame, pd.Series) else mask_or_frame
        log.append({
            "step": len(log),
            "rule": rule,
            "action": action,
            "rows_affected": len(frame),
            "pct_of_raw_lines": round(100 * len(frame) / n_raw, 2),
            "value_gbp": round(frame["line_value"].sum(), 2),
            "note": note,
        })

    per_sheet = raw["sheet"].value_counts().reindex(config.EXPECTED_SHEETS)
    record("Raw transaction lines (both sheets)", "start", raw,
           " + ".join(f"{name}: {n:,}" for name, n in per_sheet.items())
           + f"; {raw['invoice_date'].min():%Y-%m-%d %H:%M} to {raw['invoice_date'].max():%Y-%m-%d %H:%M}")

    # ---- 1-2. exact duplicates (all 8 original columns identical) ----------------
    data_cols = config.COLUMN_NAMES
    dup_any = raw.duplicated(subset=data_cols, keep="first")

    # The sheets overlap in time. Check that the overlapping lines are the same lines
    # (compared as multisets) rather than assuming it; if so, drop sheet 2's copy.
    sheet1 = raw["sheet"] == config.EXPECTED_SHEETS[0]
    sheet2 = raw["sheet"] == config.EXPECTED_SHEETS[1]
    start2, end1 = raw.loc[sheet2, "invoice_date"].min(), raw.loc[sheet1, "invoice_date"].max()
    in_window = raw["invoice_date"].between(start2, end1)

    def as_sorted(frame):
        return frame[data_cols].astype(str).sort_values(data_cols).reset_index(drop=True)

    overlap1, overlap2 = raw[sheet1 & in_window], raw[sheet2 & in_window]
    same_lines = len(overlap1) == len(overlap2) and as_sorted(overlap1).equals(as_sorted(overlap2))
    if not same_lines:
        raise ValueError("the sheets' overlapping days differ; review the overlap rule")
    overlap_copy = sheet2 & in_window
    record("Exact duplicate: sheet 2 repeats the last days of sheet 1",
           "removed", overlap_copy,
           f"{start2:%Y-%m-%d} to {end1:%Y-%m-%d} is in both sheets, identical line for line")
    rest = raw[~overlap_copy]
    repeated = pd.Series(False, index=raw.index)
    repeated[rest.index[rest.duplicated(subset=data_cols, keep="first")]] = True
    record("Exact duplicate: line repeated within the same sheet", "removed", repeated)
    df = raw[~(overlap_copy | repeated)].copy()
    assert len(df) == (~dup_any).sum(), "duplicate rules should equal a plain drop_duplicates"

    # ---- normalise text fields (no rows are dropped here) ------------------------
    code_raw = df["stock_code"]
    df["stock_code"] = code_raw.str.strip().str.upper()
    n_code_changed = int((df["stock_code"] != code_raw).sum())
    df["description"] = df["description"].str.strip().str.replace(r"\s+", " ", regex=True)

    # ---- 3. cancellations ---------------------------------------------------------
    is_cancel = df["invoice"].str.startswith("C")
    cancels = df[is_cancel].copy()
    record('Cancellation lines (Invoice starts with "C")',
           "set aside for the cancellation-rate metric", cancels)
    sales = df[~is_cancel]

    # ---- 4. non-positive quantity or price ---------------------------------------
    bad_qty_price = (sales["quantity"] <= 0) | (sales["price"] <= 0)
    record("Quantity <= 0 or price <= 0 (stock write-offs, zero-price lines, bad-debt adjustments)",
           "removed", sales[bad_qty_price])
    sales = sales[~bad_qty_price]

    # ---- 5. non-product stock codes -------------------------------------------------
    reasons = sales["stock_code"].map(non_product_reason)
    record("Non-product stock codes (postage, carriage, manual, discounts, samples, fees, vouchers, tests)",
           "removed", sales[reasons.notna()], "list in results/non_product_codes.csv")
    non_product_sales = sales[reasons.notna()]
    sales = sales[reasons.isna()].copy()

    # ---- 6. sale lines voided within 24 hours ------------------------------------
    cancels["is_product"] = cancels["stock_code"].map(non_product_reason).isna()
    paired, n_manual = match_same_day_voids(sales, cancels)
    voided = sales.index.isin(list(paired))
    record("Sale lines voided within 24 h by the same customer (identical cancellation line or "
           "a manual credit for exactly that amount) - keying errors",
           "removed; their cancellation lines are excluded from the cancellation rate",
           sales[voided], f"{len(paired) - n_manual:,} identical cancellation lines "
                          f"+ {n_manual} manual credit(s) flagged")
    # Every voided sale line next to the cancellation that voided it.
    void_log = sales.loc[list(paired), ["invoice", "invoice_date", "customer_id", "stock_code",
                                        "description", "quantity", "price", "line_value"]]
    matched = cancels.loc[list(paired.values()), ["invoice", "invoice_date", "stock_code"]]
    void_log["cancel_invoice"] = matched["invoice"].to_numpy()
    void_log["cancel_stock_code"] = matched["stock_code"].to_numpy()
    void_log["minutes_to_cancel"] = ((matched["invoice_date"].to_numpy() - void_log["invoice_date"])
                                     .dt.total_seconds() / 60).round().astype(int)
    (void_log.rename(columns={"line_value": "value_gbp"}).round({"value_gbp": 2})
     .sort_values("value_gbp", ascending=False)
     .to_csv(config.RESULTS_DIR / "voided_sales_lines.csv", index=False))
    sales = sales[~voided].copy()
    cancels["voided_within_24h"] = cancels.index.isin(list(paired.values()))

    # ---- what is left ---------------------------------------------------------------
    record("Clean product sales lines", "kept", sales,
           f"{sales['invoice'].nunique():,} invoices, {sales['stock_code'].nunique():,} products")
    no_customer = sales["customer_id"].isna()
    record("...of which: no Customer ID", "kept for revenue totals; excluded from customer analysis",
           sales[no_customer],
           f"{100 * sales.loc[no_customer, 'line_value'].sum() / sales['line_value'].sum():.1f}% "
           "of clean revenue")
    # Informational: unit prices far above the product's usual price (possible
    # mis-keyed prices, e.g. a car flag at 1,157 GBP vs a median of 0.42). Kept.
    median_price = sales.groupby("stock_code")["price"].transform("median")
    outlier = sales["price"] > 10 * median_price
    record("Unit price more than 10x the product's median price (possible mis-keyed prices)",
           "kept, flagged only", sales[outlier],
           f"{100 * sales.loc[outlier, 'line_value'].sum() / sales['line_value'].sum():.2f}% of clean "
           f"revenue; {int(sales.loc[outlier, 'customer_id'].isna().sum()):,} of these lines have no Customer ID")
    log.append({"step": len(log), "rule": "Stock code upper-cased or trimmed (e.g. '85123a' -> '85123A')",
                "action": "normalised, not removed", "rows_affected": n_code_changed,
                "pct_of_raw_lines": round(100 * n_code_changed / n_raw, 2), "value_gbp": None,
                "note": "counted on de-duplicated lines"})

    # ---- checks: every raw line is accounted for exactly once --------------------------
    clean_step = next(r["step"] for r in log if r["rule"] == "Clean product sales lines")
    removed = sum(r["rows_affected"] for r in log[1:clean_step])
    assert removed + len(sales) == n_raw, "cleaning waterfall does not add up"
    assert not sales.duplicated(subset=data_cols).any()
    assert (sales["quantity"] > 0).all() and (sales["price"] > 0).all()

    # ---- non-standard codes: what was excluded and what was kept ------------------------
    # Excluded codes: the sale lines rule 5 removed (sums to the rule-5 row above).
    # Kept codes that do not look like a standard 5-digit product code (e.g. the
    # "DCGS..." online listings): the clean sale lines they still have.
    def summarise(lines, decision):
        out = (lines.groupby("stock_code")
               .agg(sales_lines=("line_value", "size"), sales_value_gbp=("line_value", "sum"),
                    example_description=("description", lambda d: d.dropna().mode().iat[0]
                                         if d.notna().any() else ""))
               .reset_index())
        out["decision"] = decision
        return out

    kept_odd = sales[~sales["stock_code"].str.match(PRODUCT_PATTERN)]
    codes = pd.concat([summarise(non_product_sales, "excluded (not a product)"),
                       summarise(kept_odd, "kept (product)")], ignore_index=True)
    codes["reason"] = codes["stock_code"].map(non_product_reason).fillna(
        "Online (dotcom) product listing or other non-standard product code")
    codes["sales_value_gbp"] = codes["sales_value_gbp"].round(2)
    codes = codes.sort_values(["decision", "sales_lines"], ascending=[True, False])
    codes[["stock_code", "decision", "reason", "example_description", "sales_lines",
           "sales_value_gbp"]].to_csv(config.RESULTS_DIR / "non_product_codes.csv", index=False)
    assert codes.loc[codes["decision"].str.startswith("excluded"), "sales_lines"].sum() \
        == len(non_product_sales)

    # ---- write outputs ----------------------------------------------------------------------
    sales = sales.rename(columns={"line_value": "revenue"})
    sales_cols = ["invoice", "invoice_date", "customer_id", "country", "stock_code",
                  "description", "quantity", "price", "revenue"]
    sales[sales_cols].to_parquet(config.SALES_PARQUET, index=False, compression="zstd")
    cancels = cancels.rename(columns={"line_value": "value"})
    cancel_cols = ["invoice", "invoice_date", "customer_id", "country", "stock_code", "description",
                   "quantity", "price", "value", "is_product", "voided_within_24h"]
    cancels[cancel_cols].to_parquet(config.CANCELLATIONS_PARQUET, index=False, compression="zstd")
    pd.DataFrame(log).to_csv(config.RESULTS_DIR / "data_quality.csv", index=False)

    for row in log:
        value = "" if row["value_gbp"] is None else f"{row['value_gbp']:>15,.2f}"
        print(f"  {row['step']:>2}  {row['rows_affected']:>10,}  {row['pct_of_raw_lines']:>6.2f}%  "
              f"{value}  {row['rule']}")


if __name__ == "__main__":
    config.RESULTS_DIR.mkdir(exist_ok=True)
    clean()
