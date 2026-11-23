"""Step 7 - build the Excel report results/customer_analytics_report.xlsx (xlsxwriter).

Sheets
  Summary          KPI cells computed by formulas (SUM / SUMIFS / COUNTIFS / VLOOKUP) over
                   the data sheets. Each formula is written together with its cached value,
                   so file previews that do not recalculate still show the numbers.
  Monthly          monthly KPI table + a native Excel line chart
  Cohorts          retention matrix (% and counts) with a 3-colour scale, and the pooled curve
  RFM Segments     segment table built with COUNTIFS / SUMIFS / AVERAGEIFS + a bar chart
  Top Products     top 50 products and the Pareto summary
  Customers        one row per identified customer (RFM scores and segment) - the data
                   behind the Summary and RFM Segments formulas
  Data Dictionary  every column, the source and the cleaning log

Afterwards `verify()` reopens the file with openpyxl and checks the sheets, tables,
formulas, cached values, conditional format and charts.

Run:  python -I src/build_excel.py
"""
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import metrics  # noqa: E402
import segments  # noqa: E402

R = config.RESULTS_DIR
OUT = R / "customer_analytics_report.xlsx"
SHEETS = ["Summary", "Monthly", "Cohorts", "RFM Segments", "Top Products", "Customers", "Data Dictionary"]
TABLE_STYLE = "Table Style Medium 2"


def col_range(sheet: str, col: int, first_row: int, last_row: int) -> str:
    """Absolute A1 range on another sheet, e.g. 'Monthly'!$B$2:$B$26 (rows are 0-based)."""
    top = xl_rowcol_to_cell(first_row, col, row_abs=True, col_abs=True)
    bottom = xl_rowcol_to_cell(last_row, col, row_abs=True, col_abs=True)
    return f"'{sheet}'!{top}:{bottom}"


def write_table(ws, first_row, first_col, frame, name, formats=None, widths=None, style=TABLE_STYLE):
    """Write a DataFrame as an Excel table. formats: {column: format}; widths: {column: width}."""
    formats, widths = formats or {}, widths or {}
    columns = [{"header": c, "format": formats.get(c)} for c in frame.columns]
    data = frame.astype(object).where(frame.notna(), None).values.tolist()
    ws.add_table(first_row, first_col, first_row + len(frame), first_col + len(frame.columns) - 1,
                 {"name": name, "columns": columns, "data": data, "style": style})
    for j, c in enumerate(frame.columns):
        if c in widths:
            ws.set_column(first_col + j, first_col + j, widths[c])
    return first_row + 1, first_row + len(frame)   # first and last data row (0-based)


def build() -> None:
    k = metrics.as_dict()
    monthly = pd.read_csv(R / "monthly_kpis.csv", parse_dates=["month"])
    cohorts = pd.read_csv(R / "cohort_retention.csv", parse_dates=["cohort_month", "activity_month"])
    curve = pd.read_csv(R / "retention_curve.csv")
    rfm = pd.read_csv(R / "rfm_customers.csv", parse_dates=["first_purchase", "last_purchase"])
    seg = pd.read_csv(R / "rfm_segments.csv")
    ranges = pd.read_csv(R / "rfm_score_ranges.csv")
    products = pd.read_csv(R / "product_pareto.csv")
    pareto = pd.read_csv(R / "pareto_summary.csv")
    quality = pd.read_csv(R / "data_quality.csv")

    wb = xlsxwriter.Workbook(OUT, {"nan_inf_to_errors": True})
    wb.set_properties({"title": "E-commerce customer analytics", "author": "Jude (Joochan) Lee",
                       "comments": "Built by src/build_excel.py from results/*.csv"})
    f = {
        "title": wb.add_format({"bold": True, "font_size": 15, "font_color": config.NAVY}),
        "note": wb.add_format({"italic": True, "font_color": "#5B6573", "font_size": 9}),
        "label": wb.add_format({"bold": True, "font_color": config.NAVY}),
        "gbp": wb.add_format({"num_format": '"£"#,##0'}),
        "gbp2": wb.add_format({"num_format": '"£"#,##0.00'}),
        "int": wb.add_format({"num_format": "#,##0"}),
        "dec1": wb.add_format({"num_format": "0.0"}),
        "pct": wb.add_format({"num_format": "0.0%"}),
        "month": wb.add_format({"num_format": "mmm yyyy"}),
        "date": wb.add_format({"num_format": "yyyy-mm-dd"}),
        "wrap": wb.add_format({"text_wrap": True, "valign": "top"}),
        "kpi_gbp": wb.add_format({"num_format": '"£"#,##0', "bold": True, "font_size": 12}),
        "kpi_int": wb.add_format({"num_format": "#,##0", "bold": True, "font_size": 12}),
        "kpi_pct": wb.add_format({"num_format": "0.0%", "bold": True, "font_size": 12}),
        "kpi_gbp2": wb.add_format({"num_format": '"£"#,##0.00', "bold": True, "font_size": 12}),
    }
    ws = {name: wb.add_worksheet(name) for name in SHEETS}

    # ================================================================ Customers (data sheet)
    s = ws["Customers"]
    cust = rfm.rename(columns={
        "customer_id": "Customer ID", "country": "Country", "first_purchase": "First purchase",
        "last_purchase": "Last purchase", "recency_days": "Days since last order",
        "frequency": "Orders", "monetary_gbp": "Revenue (£)", "r_score": "R", "f_score": "F",
        "m_score": "M", "rfm_cell": "RFM cell", "segment": "Segment"})
    cust["RFM cell"] = cust["RFM cell"].astype(str)
    c_first, c_last = write_table(
        s, 0, 0, cust, "tblCustomers",
        formats={"First purchase": f["date"], "Last purchase": f["date"], "Revenue (£)": f["gbp2"],
                 "Orders": f["int"], "Days since last order": f["int"]},
        widths={"Customer ID": 12, "Country": 18, "First purchase": 14, "Last purchase": 14,
                "Days since last order": 12, "Orders": 9, "Revenue (£)": 13, "R": 5, "F": 5, "M": 5,
                "RFM cell": 9, "Segment": 19})
    s.freeze_panes(1, 1)
    cust_col = {name: cust.columns.get_loc(name) for name in cust.columns}
    cust_rng = {name: col_range("Customers", cust_col[name], c_first, c_last) for name in cust.columns}

    # ================================================================ Monthly
    s = ws["Monthly"]
    mon = pd.DataFrame({
        "Month": monthly["month"],
        "Revenue (£)": monthly["revenue_gbp"],
        "Orders": monthly["orders"],
        "Active customers": monthly["active_customers"],
        "New customers": monthly["new_customers"],
        "Returning customers": monthly["returning_customers"],
        "Avg order value (£)": None,                               # formula below
        "Revenue from new customers (£)": monthly["revenue_new_customers_gbp"],
        "Revenue from returning customers (£)": monthly["revenue_returning_customers_gbp"],
        "Revenue without Customer ID (£)": monthly["revenue_no_customer_id_gbp"],
        "Cancelled product value (£)": monthly["cancelled_value_gbp"],
        "Cancellation rate": None,                                  # formula below
        "Partial month": monthly["is_partial_month"].map({True: "Yes (1-9 Dec)", False: ""}),
    })
    m_first, m_last = write_table(
        s, 0, 0, mon, "tblMonthly",
        formats={"Month": f["month"], "Revenue (£)": f["gbp"], "Orders": f["int"], "Active customers": f["int"],
                 "New customers": f["int"], "Returning customers": f["int"], "Avg order value (£)": f["gbp2"],
                 "Revenue from new customers (£)": f["gbp"], "Revenue from returning customers (£)": f["gbp"],
                 "Revenue without Customer ID (£)": f["gbp"], "Cancelled product value (£)": f["gbp"],
                 "Cancellation rate": f["pct"]},
        widths={c: 14 for c in mon.columns} | {"Month": 11, "Partial month": 14})
    mc = {name: mon.columns.get_loc(name) for name in mon.columns}
    for i, row in monthly.iterrows():
        r = m_first + i
        rev, orders, canc = xl_rowcol_to_cell(r, mc["Revenue (£)"]), xl_rowcol_to_cell(r, mc["Orders"]), \
            xl_rowcol_to_cell(r, mc["Cancelled product value (£)"])
        s.write_formula(r, mc["Avg order value (£)"], f"={rev}/{orders}", f["gbp2"],
                        row["revenue_gbp"] / row["orders"])
        s.write_formula(r, mc["Cancellation rate"], f"={canc}/{rev}", f["pct"],
                        row["cancelled_value_gbp"] / row["revenue_gbp"])
    s.set_row(0, 30, f["wrap"])
    s.freeze_panes(1, 1)
    chart = wb.add_chart({"type": "line"})
    chart.add_series({
        "name": "Revenue (£)",
        "categories": ["Monthly", m_first, mc["Month"], m_last, mc["Month"]],
        "values": ["Monthly", m_first, mc["Revenue (£)"], m_last, mc["Revenue (£)"]],
        "line": {"color": config.NAVY, "width": 2},
        "marker": {"type": "circle", "size": 5, "fill": {"color": config.NAVY}, "border": {"color": "white"}},
    })
    chart.set_title({"name": "Monthly product revenue (Dec 2011 = 1-9 Dec only)",
                     "name_font": {"size": 11, "bold": True}})
    chart.set_x_axis({"date_axis": True, "num_format": "mmm yy", "major_unit": 3, "major_unit_type": "months"})
    chart.set_y_axis({"num_format": '"£"#,##0', "major_gridlines": {"visible": True, "line": {"color": "#E3E6EA"}}})
    chart.set_legend({"none": True})
    chart.set_size({"width": 760, "height": 380})
    s.insert_chart(m_last + 3, 0, chart)

    def mrange(name):
        return col_range("Monthly", mc[name], m_first, m_last)

    # ================================================================ Cohorts
    s = ws["Cohorts"]
    s.write(0, 0, "Cohort retention: share of each first-purchase cohort that ordered in a later month",
            f["title"])
    s.write(1, 0, "Rows = month of first purchase (cohort); M1..M24 = months after it (M0 = 100%). Blank = not "
                  "observed yet: December 2011 has only 1-9 Dec, so it is left out. *Dec 2009 also contains "
                  "established customers (the data starts on 1 Dec 2009).", f["note"])
    last_full = monthly.loc[~monthly["is_partial_month"], "month"].max()
    sizes = cohorts[cohorts["months_since_first"] == 0].set_index("cohort_month")["cohort_size"]
    pct_grid = cohorts.pivot(index="cohort_month", columns="months_since_first", values="retention_pct") / 100
    cnt_grid = cohorts.pivot(index="cohort_month", columns="months_since_first", values="active_customers")
    pct_grid = pct_grid.reindex(columns=range(25))
    cnt_grid = cnt_grid.reindex(columns=range(25))
    for cohort in pct_grid.index:                      # observed-but-zero vs not observed
        for kk in range(25):
            observed = cohort + pd.DateOffset(months=kk) <= last_full
            if not observed:
                pct_grid.loc[cohort, kk] = None
                cnt_grid.loc[cohort, kk] = None
            elif pd.isna(cnt_grid.loc[cohort, kk]):
                pct_grid.loc[cohort, kk], cnt_grid.loc[cohort, kk] = 0.0, 0
    labels = [f"{d:%b %Y}" + ("*" if n == 0 else "") for n, d in enumerate(pct_grid.index)]
    pct_tbl = pd.concat([pd.DataFrame({"Cohort": labels, "Customers": sizes.values}),
                         pct_grid.reset_index(drop=True).set_axis([f"M{i}" for i in range(25)], axis=1)], axis=1)
    cnt_tbl = pd.concat([pd.DataFrame({"Cohort": labels, "Customers": sizes.values}),
                         cnt_grid.reset_index(drop=True).set_axis([f"M{i}" for i in range(25)], axis=1)], axis=1)
    month_cols = [f"M{i}" for i in range(25)]
    p_first, p_last = write_table(s, 3, 0, pct_tbl, "tblRetentionPct",
                                  formats={c: f["pct"] for c in month_cols} | {"Customers": f["int"]},
                                  widths={"Cohort": 11, "Customers": 10} | {c: 6.5 for c in month_cols})
    s.conditional_format(p_first, 3, p_last, 2 + 24, {      # M1..M24 (M0 is always 100%)
        "type": "3_color_scale",
        "min_type": "num", "min_value": 0, "min_color": "#FFFFFF",
        "mid_type": "percentile", "mid_value": 50, "mid_color": "#BFE3DE",
        "max_type": "max", "max_color": config.TEAL})
    s.write(p_last + 2, 0, "Active customers (counts behind the percentages above)", f["label"])
    c_tbl_first, c_tbl_last = write_table(s, p_last + 3, 0, cnt_tbl, "tblRetentionCounts",
                                          formats={c: f["int"] for c in month_cols} | {"Customers": f["int"]})
    s.write(c_tbl_last + 2, 0, "Pooled retention curve (cohorts Jan 2010 onwards, months fully observed)",
            f["label"])
    curve_tbl = pd.DataFrame({
        "Months after first purchase": curve["months_since_first"],
        "Cohorts included": curve["cohorts_included"],
        "Customers in cohorts": curve["customers_in_cohorts"],
        "Active customers": curve["active_customers"],
        "Retention": curve["retention_pct"] / 100,
    })
    cv_first, cv_last = write_table(s, c_tbl_last + 3, 0, curve_tbl, "tblRetentionCurve",
                                    formats={"Retention": f["pct"], "Customers in cohorts": f["int"],
                                             "Active customers": f["int"]})
    s.set_row(3, 18)
    s.freeze_panes(4, 2)
    curve_range = (f"'Cohorts'!{xl_rowcol_to_cell(cv_first, 0, True, True)}:"
                   f"{xl_rowcol_to_cell(cv_last, 4, True, True)}")

    # ================================================================ RFM Segments
    s = ws["RFM Segments"]
    s.write(0, 0, "RFM segments: who the valuable customers are and what to do next", f["title"])
    s.write(1, 0, "Scores 1-5 (5 = most recent, most orders, most spend); rules are applied top to bottom. "
                  "Customers, revenue and averages are formulas over the Customers sheet.", f["note"])
    seg_tbl = pd.DataFrame({
        "Segment": seg["segment"],
        "Rule (R, F, M scores)": seg["rule"],
        "What it means": [next(x["meaning"] for x in segments.SEGMENTS if x["segment"] == n)
                          for n in seg["segment"]],
        "Customers": None, "% of customers": None, "Revenue (£)": None, "% of revenue": None,
        "Avg revenue per customer (£)": None, "Avg orders": None,
        "Median revenue per customer (£)": seg["median_revenue_per_customer_gbp"],
        "Median days since last order": seg["median_days_since_last_order"],
        "Action": seg["action"],
    })
    s_first, s_last = write_table(
        s, 3, 0, seg_tbl, "tblSegments",
        formats={"Customers": f["int"], "% of customers": f["pct"], "Revenue (£)": f["gbp"],
                 "% of revenue": f["pct"], "Avg revenue per customer (£)": f["gbp"], "Avg orders": f["dec1"],
                 "Median revenue per customer (£)": f["gbp"], "Median days since last order": f["int"]},
        widths={"Segment": 19, "Rule (R, F, M scores)": 30, "What it means": 44, "Customers": 11,
                "% of customers": 12, "Revenue (£)": 14, "% of revenue": 11, "Avg revenue per customer (£)": 14,
                "Avg orders": 9, "Median revenue per customer (£)": 14, "Median days since last order": 13,
                "Action": 70})
    sc = {name: seg_tbl.columns.get_loc(name) for name in seg_tbl.columns}
    total_customers, total_revenue = len(rfm), rfm["monetary_gbp"].sum()
    for i, row in seg.iterrows():
        r = s_first + i
        name_cell = xl_rowcol_to_cell(r, sc["Segment"])
        n = int((rfm["segment"] == row["segment"]).sum())
        rev = rfm.loc[rfm["segment"] == row["segment"], "monetary_gbp"].sum()
        orders = rfm.loc[rfm["segment"] == row["segment"], "frequency"].mean()
        cust_cell = xl_rowcol_to_cell(r, sc["Customers"])
        rev_cell = xl_rowcol_to_cell(r, sc["Revenue (£)"])
        s.write_formula(r, sc["Customers"], f"=COUNTIFS({cust_rng['Segment']},{name_cell})", f["int"], n)
        s.write_formula(r, sc["% of customers"], f"={cust_cell}/COUNT({cust_rng['Customer ID']})",
                        f["pct"], n / total_customers)
        s.write_formula(r, sc["Revenue (£)"],
                        f"=SUMIFS({cust_rng['Revenue (£)']},{cust_rng['Segment']},{name_cell})", f["gbp"], rev)
        s.write_formula(r, sc["% of revenue"], f"={rev_cell}/SUM({cust_rng['Revenue (£)']})",
                        f["pct"], rev / total_revenue)
        s.write_formula(r, sc["Avg revenue per customer (£)"], f"={rev_cell}/{cust_cell}", f["gbp"], rev / n)
        s.write_formula(r, sc["Avg orders"],
                        f"=AVERAGEIFS({cust_rng['Orders']},{cust_rng['Segment']},{name_cell})", f["dec1"], orders)
    s.set_row(3, 30, f["wrap"])
    s.freeze_panes(4, 1)
    chart = wb.add_chart({"type": "bar"})
    for col, color in (("% of customers", config.GRAY), ("% of revenue", config.NAVY)):
        chart.add_series({
            "name": ["RFM Segments", 3, sc[col]],
            "categories": ["RFM Segments", s_first, sc["Segment"], s_last, sc["Segment"]],
            "values": ["RFM Segments", s_first, sc[col], s_last, sc[col]],
            "fill": {"color": color}, "gap": 60,
        })
    chart.set_title({"name": "Share of customers vs share of revenue by segment",
                     "name_font": {"size": 11, "bold": True}})
    chart.set_x_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E3E6EA"}}})
    chart.set_y_axis({"reverse": True})
    chart.set_legend({"position": "bottom"})
    chart.set_size({"width": 760, "height": 420})
    s.insert_chart(s_last + 3, 0, chart)
    s.write(s_last + 25, 0, "What each score means", f["label"])
    rng_tbl = pd.DataFrame({
        "Score": ranges["score"],
        "R: customers": ranges["r_customers"],
        "R: days since last order": [f"{a}-{b}" for a, b in zip(ranges["r_min_days"], ranges["r_max_days"])],
        "F: customers": ranges["f_customers"],
        "F: orders": [f"{a}" if a == b else f"{a}-{b}" for a, b in
                      zip(ranges["f_min_orders"], ranges["f_max_orders"])],
        "M: customers": ranges["m_customers"],
        "M: revenue (£)": [f"{a:,.0f}-{b:,.0f}" for a, b in zip(ranges["m_min_gbp"], ranges["m_max_gbp"])],
    })
    write_table(s, s_last + 26, 0, rng_tbl, "tblScoreRanges",
                formats={"R: customers": f["int"], "F: customers": f["int"], "M: customers": f["int"]})

    # ================================================================ Top Products
    s = ws["Top Products"]
    s.write(0, 0, "Top 50 products by revenue (product = stock code)", f["title"])
    s.write(1, 0, f"{len(products):,} products sold; the Pareto summary on the right covers all of them.",
            f["note"])
    top = products.head(50)
    top_tbl = pd.DataFrame({
        "Rank": top["revenue_rank"], "Stock code": top["stock_code"].astype(str),
        "Description": top["description"], "Revenue (£)": top["revenue_gbp"],
        "% of revenue": top["pct_of_revenue"] / 100, "Cumulative % of revenue": top["cumulative_pct_of_revenue"] / 100,
        "Units": top["units"], "Orders": top["orders"], "Customers": top["customers"]})
    write_table(s, 3, 0, top_tbl, "tblTopProducts",
                formats={"Revenue (£)": f["gbp"], "% of revenue": f["pct"], "Cumulative % of revenue": f["pct"],
                         "Units": f["int"], "Orders": f["int"], "Customers": f["int"]},
                widths={"Rank": 6, "Stock code": 10, "Description": 38, "Revenue (£)": 12, "% of revenue": 10,
                        "Cumulative % of revenue": 12, "Units": 10, "Orders": 9, "Customers": 10})
    par_tbl = pd.DataFrame({"Measure": pareto["measure"], "Products": pareto["products"],
                            "% of products": pareto["pct_of_products"] / 100,
                            "% of revenue": pareto["pct_of_revenue"] / 100})
    par_first, par_last = write_table(s, 3, 10, par_tbl, "tblPareto",
                                      formats={"Products": f["int"], "% of products": f["pct"],
                                               "% of revenue": f["pct"]},
                                      widths={"Measure": 34, "Products": 9, "% of products": 11, "% of revenue": 11})
    s.set_row(3, 30, f["wrap"])
    s.freeze_panes(4, 0)
    pareto_range = (f"'Top Products'!{xl_rowcol_to_cell(par_first, 10, True, True)}:"
                    f"{xl_rowcol_to_cell(par_last, 13, True, True)}")

    # ================================================================ Data Dictionary
    s = ws["Data Dictionary"]
    s.write(0, 0, "Data dictionary and data notes", f["title"])
    notes = [
        ("Source", "UCI Machine Learning Repository, 'Online Retail II' (dataset 502), "
                   "https://archive.ics.uci.edu/dataset/502/online+retail+ii"),
        ("License", "Creative Commons Attribution 4.0 International (CC BY 4.0)"),
        ("Coverage", "Transactions from 1 Dec 2009 to 9 Dec 2011 of a UK-based online gift retailer "
                     "(many customers are wholesalers). December 2011 holds 1-9 Dec only."),
        ("Revenue", "Quantity x unit price (GBP) of product sale lines after cleaning; cancellations are "
                    "tracked separately (see cancellation rate)."),
        ("Customers", "Identified customers only (lines with a Customer ID). Lines without one count in "
                      "revenue totals but not in cohorts, RFM or segments."),
        ("Rebuild", "python -I src/run_all.py rebuilds every number and this workbook from the raw download."),
    ]
    for i, (a, b) in enumerate(notes):
        s.write(2 + i, 0, a, f["label"])
        s.write(2 + i, 1, b)
    dictionary = [
        ("Summary", "KPI / Value / How it is calculated",
         "Headline KPIs; every value is a live formula over the data sheets."),
        ("Monthly", "Month", "Calendar month of the invoice date."),
        ("Monthly", "Revenue (£)", "Product revenue in the month, including lines with no Customer ID."),
        ("Monthly", "Orders", "Distinct invoices with at least one product line."),
        ("Monthly", "Active customers", "Identified customers with an order in the month."),
        ("Monthly", "New customers", "Identified customers whose first order in the data is in the month."),
        ("Monthly", "Returning customers", "Active customers who had ordered in an earlier month."),
        ("Monthly", "Avg order value (£)", "Revenue / Orders (formula)."),
        ("Monthly", "Revenue from new / returning customers (£)",
         "Revenue split by whether the customer's first month is this month or earlier."),
        ("Monthly", "Revenue without Customer ID (£)", "Revenue from lines with no Customer ID."),
        ("Monthly", "Cancelled product value (£)",
         "Value of product cancellation lines (invoice starting with C), excluding same-day keying-error voids."),
        ("Monthly", "Cancellation rate", "Cancelled product value / Revenue (formula)."),
        ("Cohorts", "Cohort / Customers", "Month of first purchase and the number of customers in it."),
        ("Cohorts", "M0..M24", "Share (or count) of the cohort that ordered N months after the first month."),
        ("Cohorts", "Pooled retention curve",
         "Active / cohort customers summed over cohorts from Jan 2010 that were fully observed at month N."),
        ("RFM Segments", "Rule (R, F, M scores)",
         "R = recency score, F = number of orders score, M = revenue score; 1-5, 5 is best."),
        ("RFM Segments", "Customers, % of customers, Revenue, % of revenue, Avg revenue, Avg orders",
         "COUNTIFS / SUMIFS / AVERAGEIFS formulas over the Customers sheet."),
        ("RFM Segments", "Median revenue per customer, Median days since last order",
         "Values from results/rfm_segments.csv (medians need array formulas in older Excel)."),
        ("Top Products", "Rank / Stock code / Description",
         "Products ranked by revenue; description = the most common description of the stock code."),
        ("Top Products", "% of revenue / Cumulative % of revenue", "Share of all product revenue, running total."),
        ("Customers", "Days since last order", "Days from the last order to 10 Dec 2011 (day after the data ends)."),
        ("Customers", "Orders", "Distinct invoices over Dec 2009-Dec 2011."),
        ("Customers", "Revenue (£)", "Product revenue over Dec 2009-Dec 2011."),
        ("Customers", "R, F, M", "NTILE(5) scores; tied values share the lower score."),
        ("Customers", "Segment", "First matching rule in the RFM Segments sheet."),
    ]
    dict_tbl = pd.DataFrame(dictionary, columns=["Sheet", "Column", "Definition"])
    d_first, d_last = write_table(s, 9, 0, dict_tbl, "tblDictionary",
                                  widths={"Sheet": 15, "Column": 44, "Definition": 100})
    s.write(d_last + 2, 0, "Cleaning log (results/data_quality.csv)", f["label"])
    dq = quality.rename(columns={"step": "Step", "rule": "Rule", "action": "Action",
                                 "rows_affected": "Rows", "pct_of_raw_lines": "% of raw lines",
                                 "value_gbp": "Value (£)", "note": "Note"})
    dq["% of raw lines"] = dq["% of raw lines"] / 100
    write_table(s, d_last + 3, 0, dq, "tblDataQuality",
                formats={"Rows": f["int"], "% of raw lines": f["pct"], "Value (£)": f["gbp"]})
    s.set_column(3, 3, 12)
    s.set_column(4, 6, 14)

    # ================================================================ Summary (formulas)
    s = ws["Summary"]
    s.write(0, 0, "E-commerce customer analytics: UK online gift retailer", f["title"])
    s.write(1, 0, "Data: 1 Dec 2009 - 9 Dec 2011, UCI Online Retail II (CC BY 4.0). Every value below is a "
                  "formula over the other sheets (SUM, SUMIFS, COUNTIFS, VLOOKUP).", f["note"])
    rev_m, months_m = mrange("Revenue (£)"), mrange("Month")

    def between(start, end):
        return (f'SUMIFS({rev_m},{months_m},">="&DATE({start[0]},{start[1]},1),'
                f'{months_m},"<="&DATE({end[0]},{end[1]},1))')

    def monthly_sum(start, end):
        sel = (monthly["month"] >= pd.Timestamp(*start, 1)) & (monthly["month"] <= pd.Timestamp(*end, 1))
        return monthly.loc[sel, "revenue_gbp"].sum()

    first_row = 4                                    # table header on row 4 (0-based 3)
    cell = {}                                        # KPI name -> its value cell (for later formulas)

    def kpi_cell(i):
        return xl_rowcol_to_cell(first_row + i, 1)

    is_repeat = rfm["frequency"] >= 2
    kpis = [
        ("Product revenue (£)", f"=SUM({rev_m})", "kpi_gbp", monthly["revenue_gbp"].sum(),
         "Sum of Monthly revenue"),
        ("Orders", f"=SUM({mrange('Orders')})", "kpi_int", monthly["orders"].sum(), "Sum of Monthly orders"),
        ("Average order value (£)", "={rev}/{orders}", "kpi_gbp2",
         monthly["revenue_gbp"].sum() / monthly["orders"].sum(), "Revenue / orders"),
        ("Identified customers", f"=COUNT({cust_rng['Customer ID']})", "kpi_int", len(rfm),
         "Customers sheet rows"),
        ("Customers with 2+ orders", f'=COUNTIFS({cust_rng["Orders"]},">=2")/{{customers}}', "kpi_pct",
         is_repeat.mean(), "COUNTIFS(orders >= 2) / customers"),
        ("Revenue from customers with 2+ orders",
         f'=SUMIFS({cust_rng["Revenue (£)"]},{cust_rng["Orders"]},">=2")/SUM({cust_rng["Revenue (£)"]})',
         "kpi_pct", rfm.loc[is_repeat, "monetary_gbp"].sum() / total_revenue, "SUMIFS / SUM on Customers"),
        ("Revenue growth, Jan-Nov 2011 vs Jan-Nov 2010",
         f"={between((2011, 1), (2011, 11))}/{between((2010, 1), (2010, 11))}-1", "kpi_pct",
         monthly_sum((2011, 1), (2011, 11)) / monthly_sum((2010, 1), (2010, 11)) - 1,
         "SUMIFS by month on Monthly"),
        ("Sep-Nov share of the last 12 full months (Dec 2010-Nov 2011)",
         f"={between((2011, 9), (2011, 11))}/{between((2010, 12), (2011, 11))}", "kpi_pct",
         monthly_sum((2011, 9), (2011, 11)) / monthly_sum((2010, 12), (2011, 11)), "SUMIFS by month on Monthly"),
        ("Champions: share of customers", f'=COUNTIFS({cust_rng["Segment"]},"Champions")/{{customers}}',
         "kpi_pct", (rfm["segment"] == "Champions").mean(), "COUNTIFS(segment) / customers"),
        ("Champions: share of revenue",
         f'=SUMIFS({cust_rng["Revenue (£)"]},{cust_rng["Segment"]},"Champions")/SUM({cust_rng["Revenue (£)"]})',
         "kpi_pct", rfm.loc[rfm["segment"] == "Champions", "monetary_gbp"].sum() / total_revenue,
         "SUMIFS(segment) / SUM"),
        ("Can't Lose + At Risk: past revenue (£)",
         f'=SUMIFS({cust_rng["Revenue (£)"]},{cust_rng["Segment"]},"Can\'t Lose")'
         f'+SUMIFS({cust_rng["Revenue (£)"]},{cust_rng["Segment"]},"At Risk")', "kpi_gbp",
         rfm.loc[rfm["segment"].isin(["Can't Lose", "At Risk"]), "monetary_gbp"].sum(),
         "Revenue of customers who have gone quiet"),
        ("Month-1 retention of new customers (pooled)",
         f"=VLOOKUP(1,{curve_range},4,FALSE)/VLOOKUP(1,{curve_range},3,FALSE)", "kpi_pct",
         curve.loc[curve["months_since_first"] == 1, "active_customers"].iat[0]
         / curve.loc[curve["months_since_first"] == 1, "customers_in_cohorts"].iat[0],
         "VLOOKUP on the Cohorts retention curve"),
        ("Top 20% of products: share of revenue",
         f'=VLOOKUP("top 20% of products",{pareto_range},4,FALSE)', "kpi_pct",
         pareto.loc[pareto["measure"] == "top 20% of products", "pct_of_revenue"].iat[0] / 100,
         "VLOOKUP on the Top Products Pareto table"),
        ("Revenue without a Customer ID", f"=SUM({mrange('Revenue without Customer ID (£)')})/SUM({rev_m})",
         "kpi_pct", monthly["revenue_no_customer_id_gbp"].sum() / monthly["revenue_gbp"].sum(),
         "Not usable for customer analysis"),
        ("Product cancellation rate", f"=SUM({mrange('Cancelled product value (£)')})/SUM({rev_m})", "kpi_pct",
         monthly["cancelled_value_gbp"].sum() / monthly["revenue_gbp"].sum(), "Cancelled value / revenue"),
    ]
    names = [x[0] for x in kpis]
    cell["rev"], cell["orders"], cell["customers"] = (kpi_cell(names.index("Product revenue (£)")),
                                                      kpi_cell(names.index("Orders")),
                                                      kpi_cell(names.index("Identified customers")))
    s.add_table(first_row - 1, 0, first_row - 1 + len(kpis), 2,
                {"name": "tblKPI", "style": TABLE_STYLE,
                 "columns": [{"header": "KPI"}, {"header": "Value"}, {"header": "How it is calculated"}]})
    for i, (name, formula, fmt, value, how) in enumerate(kpis):
        formula = formula.replace("{rev}", cell["rev"]).replace("{orders}", cell["orders"]) \
                         .replace("{customers}", cell["customers"])
        s.write(first_row + i, 0, name)
        s.write_formula(first_row + i, 1, formula, f[fmt], value)
        s.write(first_row + i, 2, how, f["note"])
    s.set_column(0, 0, 58)
    s.set_column(1, 1, 18)
    s.set_column(2, 2, 44)
    s.freeze_panes(first_row, 0)
    s.activate()
    wb.close()
    print(f"  wrote {OUT.relative_to(config.ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)")

    # The cached values must equal the headline metrics (they come from the same CSVs).
    expected = {"Product revenue (£)": k["revenue_total_gbp"],
                "Champions: share of revenue": k["seg_champions_revenue_pct"] / 100,
                "Customers with 2+ orders": k["repeat_customers_pct"] / 100,
                "Month-1 retention of new customers (pooled)": k["retention_month_1_pct"] / 100}
    for name, value in expected.items():
        cached = kpis[names.index(name)][3]
        assert abs(cached - value) < 1e-4 * max(1, abs(value)), (name, cached, value)


def verify(path: Path = OUT) -> None:
    """Reopen the workbook with openpyxl and check what a reader relies on."""
    from openpyxl import load_workbook

    wb = load_workbook(path)                       # formulas
    cached = load_workbook(path, data_only=True)   # cached values
    assert wb.sheetnames == SHEETS, wb.sheetnames
    expected_tables = {
        "Summary": {"tblKPI"}, "Monthly": {"tblMonthly"},
        "Cohorts": {"tblRetentionPct", "tblRetentionCounts", "tblRetentionCurve"},
        "RFM Segments": {"tblSegments", "tblScoreRanges"}, "Top Products": {"tblTopProducts", "tblPareto"},
        "Customers": {"tblCustomers"}, "Data Dictionary": {"tblDictionary", "tblDataQuality"},
    }
    report = []
    for sheet, tables in expected_tables.items():
        ws, wsc = wb[sheet], cached[sheet]
        missing = tables - set(ws.tables.keys())
        assert not missing, f"{sheet}: missing tables {missing}"
        formulas = [(c.coordinate, c.value) for row in ws.iter_rows() for c in row
                    if isinstance(c.value, str) and c.value.startswith("=")]
        no_cache = [coord for coord, _ in formulas if wsc[coord].value is None]
        assert not no_cache, f"{sheet}: formulas without cached values {no_cache[:5]}"
        report.append(f"{sheet}: {len(ws.tables)} table(s), {len(formulas)} formula(s), freeze {ws.freeze_panes}")
    # Every range a Summary / RFM Segments formula reads must start under the intended
    # column header and end on the table's last data row (nothing left out).
    allowed = {"Revenue (£)", "Orders", "Customer ID", "Month", "Segment", "Revenue without Customer ID (£)",
               "Cancelled product value (£)", "Months after first purchase", "Measure"}
    ref = re.compile(r"'([^']+)'!\$([A-Z]+)\$(\d+):\$([A-Z]+)\$(\d+)")
    checked = set()
    for sheet in ("Summary", "RFM Segments"):
        for row in wb[sheet].iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    for target, col1, row1, _, row2 in ref.findall(c.value):
                        header = wb[target][f"{col1}{int(row1) - 1}"].value
                        after = wb[target][f"{col1}{int(row2) + 1}"].value
                        assert header in allowed and after is None, (sheet, c.coordinate, header, after)
                        checked.add((target, col1, row1, row2))
    summary = wb["Summary"]
    functions = " ".join(str(c.value) for c in summary["B"] if isinstance(c.value, str))
    for fn in ("SUM(", "SUMIFS(", "COUNTIFS(", "VLOOKUP(", "COUNT("):
        assert fn in functions, f"Summary has no {fn} formula"
    rules = [r for cf in wb["Cohorts"].conditional_formatting for r in cf.rules]
    assert any(r.type == "colorScale" and len(r.colorScale.cfvo) == 3 for r in rules), "no 3-colour scale"
    with zipfile.ZipFile(path) as z:
        charts = [n for n in z.namelist() if n.startswith("xl/charts/chart")]
    assert len(charts) == 2, charts
    print("  verified with openpyxl:")
    for line in report:
        print(f"    {line}")
    print(f"    Cohorts: 3-colour scale present; {len(charts)} native charts in the file")
    print(f"    {len(checked)} formula ranges point at the intended column and cover the whole table")


if __name__ == "__main__":
    build()
    verify()
