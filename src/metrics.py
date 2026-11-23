"""Step 5 - collect the headline numbers into results/key_metrics.csv.

Every number quoted in the README comes from this file (or directly from another
CSV in results/). Each metric is derived from a results/ CSV - never typed in - and
the row says which file it came from and how.

Run:  python -I src/metrics.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

R = config.RESULTS_DIR


def load(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(R / f"{name}.csv", **kwargs)


def compute() -> pd.DataFrame:
    rows = []

    def add(metric, value, unit, source, how):
        rows.append({"metric": metric, "value": value, "unit": unit, "source": source, "how": how})

    # ---------------------------------------------------------------- data & cleaning
    dq = load("data_quality").set_index("step")
    raw_lines = int(dq.loc[0, "rows_affected"])
    clean = dq[dq["rule"] == "Clean product sales lines"].iloc[0]
    no_id = dq[dq["rule"].str.startswith("...of which: no Customer ID")].iloc[0]
    voids = dq[dq["rule"].str.startswith("Sale lines voided")].iloc[0]
    dups = dq[dq["rule"].str.startswith("Exact duplicate")]
    add("raw_lines", raw_lines, "lines", "data_quality.csv", "step 0")
    add("clean_sales_lines", int(clean["rows_affected"]), "lines", "data_quality.csv", "clean step")
    add("clean_pct_of_raw_lines", clean["pct_of_raw_lines"], "%", "data_quality.csv", "clean step")
    add("duplicate_lines_removed", int(dups["rows_affected"].sum()), "lines", "data_quality.csv",
        "sum of the two exact-duplicate steps")
    add("voided_sale_lines", int(voids["rows_affected"]), "lines", "data_quality.csv", "void step")
    add("voided_sale_value_gbp", voids["value_gbp"], "GBP", "data_quality.csv", "void step")
    top_voids = load("voided_sales_lines").head(2)
    add("two_largest_voids_value_gbp", round(top_voids["value_gbp"].sum(), 2), "GBP",
        "voided_sales_lines.csv", "sum of the 2 largest voided lines")
    add("no_customer_id_lines_pct_of_clean", round(100 * no_id["rows_affected"] / clean["rows_affected"], 2),
        "%", "data_quality.csv", "no-ID lines / clean lines")

    # ---------------------------------------------------------------- overall & monthly
    m = load("monthly_kpis", parse_dates=["month"])
    total_rev = m["revenue_gbp"].sum()
    add("revenue_total_gbp", round(total_rev, 2), "GBP", "monthly_kpis.csv", "sum of revenue_gbp")
    add("orders_total", int(m["orders"].sum()), "orders", "monthly_kpis.csv", "sum of orders")
    add("avg_order_value_gbp", round(total_rev / m["orders"].sum(), 2), "GBP", "monthly_kpis.csv",
        "revenue / orders")
    add("no_customer_id_revenue_pct", round(100 * m["revenue_no_customer_id_gbp"].sum() / total_rev, 2),
        "%", "monthly_kpis.csv", "no-ID revenue / revenue")
    nov = m[m["month"].dt.month == 11]
    add("november_no_customer_id_revenue_pct",
        round(100 * nov["revenue_no_customer_id_gbp"].sum() / nov["revenue_gbp"].sum(), 2), "%",
        "monthly_kpis.csv", "Nov 2010 + Nov 2011 no-ID revenue / their revenue")

    def window(start, end):  # inclusive month range
        return m[(m["month"] >= start) & (m["month"] <= end)]

    jan_nov_2010 = window("2010-01-01", "2010-11-01")["revenue_gbp"].sum()
    jan_nov_2011 = window("2011-01-01", "2011-11-01")["revenue_gbp"].sum()
    add("revenue_jan_nov_2010_gbp", round(jan_nov_2010, 2), "GBP", "monthly_kpis.csv", "Jan-Nov 2010")
    add("revenue_jan_nov_2011_gbp", round(jan_nov_2011, 2), "GBP", "monthly_kpis.csv", "Jan-Nov 2011")
    add("revenue_growth_jan_nov_pct", round(100 * (jan_nov_2011 / jan_nov_2010 - 1), 2), "%",
        "monthly_kpis.csv", "Jan-Nov 2011 vs Jan-Nov 2010")
    last12 = window("2010-12-01", "2011-11-01")
    autumn = window("2011-09-01", "2011-11-01")["revenue_gbp"].sum()
    add("revenue_dec2010_nov2011_gbp", round(last12["revenue_gbp"].sum(), 2), "GBP", "monthly_kpis.csv",
        "last 12 full months")
    add("sep_nov_share_of_12_months_pct", round(100 * autumn / last12["revenue_gbp"].sum(), 2), "%",
        "monthly_kpis.csv", "Sep-Nov 2011 / Dec 2010-Nov 2011")
    full = m[~m["is_partial_month"]]
    peak, trough = full.loc[full["revenue_gbp"].idxmax()], full.loc[full["revenue_gbp"].idxmin()]
    add("peak_month", peak["month"].strftime("%b %Y"), "", "monthly_kpis.csv", "highest full month")
    add("peak_month_revenue_gbp", peak["revenue_gbp"], "GBP", "monthly_kpis.csv", "highest full month")
    add("nov_2010_revenue_gbp", window("2010-11-01", "2010-11-01")["revenue_gbp"].iat[0], "GBP",
        "monthly_kpis.csv", "")
    add("lowest_month", trough["month"].strftime("%b %Y"), "", "monthly_kpis.csv", "lowest full month")
    add("lowest_month_revenue_gbp", trough["revenue_gbp"], "GBP", "monthly_kpis.csv", "lowest full month")
    add("peak_to_lowest_ratio", round(peak["revenue_gbp"] / trough["revenue_gbp"], 2), "x",
        "monthly_kpis.csv", "peak / lowest full month")
    y2011 = m[m["month"].dt.year == 2011]
    identified_2011 = y2011["revenue_new_customers_gbp"].sum() + y2011["revenue_returning_customers_gbp"].sum()
    add("returning_share_of_identified_revenue_2011_pct",
        round(100 * y2011["revenue_returning_customers_gbp"].sum() / identified_2011, 2), "%",
        "monthly_kpis.csv", "2011 returning-customer revenue / identified revenue")
    add("product_cancellation_rate_pct", round(100 * m["cancelled_value_gbp"].sum() / total_rev, 2), "%",
        "monthly_kpis.csv", "cancelled product value / product revenue (same-day voids excluded)")

    # ---------------------------------------------------------------- customers & retention
    rfm = load("rfm_customers")
    add("customers_identified", len(rfm), "customers", "rfm_customers.csv", "rows")
    repeat = rfm["frequency"] >= 2
    add("repeat_customers_pct", round(100 * repeat.mean(), 2), "%", "rfm_customers.csv",
        "customers with 2+ orders / customers")
    add("repeat_customers_revenue_pct",
        round(100 * rfm.loc[repeat, "monetary_gbp"].sum() / rfm["monetary_gbp"].sum(), 2), "%",
        "rfm_customers.csv", "their share of identified revenue")
    add("single_order_customers_pct", round(100 * (~repeat).mean(), 2), "%", "rfm_customers.csv", "")
    add("single_order_customers_revenue_pct",
        round(100 * rfm.loc[~repeat, "monetary_gbp"].sum() / rfm["monetary_gbp"].sum(), 2), "%",
        "rfm_customers.csv", "")
    ranked = rfm.sort_values("monetary_gbp", ascending=False)
    top1 = int(-(-len(rfm) // 100))  # ceil(1% of customers)
    add("top_1pct_customers", top1, "customers", "rfm_customers.csv", "ceil(1% of customers)")
    add("top_1pct_customers_revenue_pct",
        round(100 * ranked["monetary_gbp"].head(top1).sum() / rfm["monetary_gbp"].sum(), 2), "%",
        "rfm_customers.csv", "")
    add("top_10_customers_revenue_pct",
        round(100 * ranked["monetary_gbp"].head(10).sum() / rfm["monetary_gbp"].sum(), 2), "%",
        "rfm_customers.csv", "")

    curve = load("retention_curve").set_index("months_since_first")
    for k in (1, 3, 6, 10, 11, 12):
        add(f"retention_month_{k}_pct", curve.loc[k, "retention_pct"], "%", "retention_curve.csv",
            "pooled over cohorts Jan 2010+ fully observed at that month")
    cohorts = load("cohort_retention")
    dec09 = cohorts[(cohorts["cohort_month"] == cohorts["cohort_month"].min())
                    & (cohorts["months_since_first"] == 1)]
    add("dec2009_cohort_month_1_pct", dec09["retention_pct"].iat[0], "%", "cohort_retention.csv",
        "first cohort, month 1")

    timing = load("repeat_purchase_timing").set_index("days_since_first_purchase")
    add("new_customers_with_1y_followup", int(timing["new_customers"].iat[0]), "customers",
        "repeat_purchase_timing.csv", "first purchase Jan 2010 - 9 Dec 2010")
    for d in (30, 60, 90, 180, 365):
        add(f"reordered_within_{d}d_pct", timing.loc[d, "pct_returned"], "%", "repeat_purchase_timing.csv", "")
    returners = timing.loc[365, "returned_customers"]
    median_day = int(timing.index[timing["returned_customers"] >= returners / 2][0])
    add("median_days_to_second_order_returners", median_day, "days", "repeat_purchase_timing.csv",
        "first day by which half of the 365-day returners had come back")

    fyv = load("first_year_value").set_index("first_purchase_month")
    allv = fyv.loc["All eligible"]
    add("first_year_value_median_gbp", allv["median_revenue_365d_gbp"], "GBP", "first_year_value.csv", "")
    add("first_year_value_mean_gbp", allv["avg_revenue_365d_gbp"], "GBP", "first_year_value.csv", "")
    add("first_year_revenue_after_first_day_pct", allv["pct_of_365d_revenue_after_first_day"], "%",
        "first_year_value.csv", "")

    # ---------------------------------------------------------------- segments
    seg = load("rfm_segments").set_index("segment")
    for name in seg.index:
        key = name.lower().replace("'", "").replace(" ", "_")
        add(f"seg_{key}_customers", int(seg.loc[name, "customers"]), "customers", "rfm_segments.csv", "")
        add(f"seg_{key}_customers_pct", seg.loc[name, "pct_of_customers"], "%", "rfm_segments.csv", "")
        add(f"seg_{key}_revenue_pct", seg.loc[name, "pct_of_revenue"], "%", "rfm_segments.csv", "")
    pairs = {"champions_loyal": ["Champions", "Loyal"], "cant_lose_at_risk": ["Can't Lose", "At Risk"],
             "hibernating_lost": ["Hibernating", "Lost"]}
    for key, names in pairs.items():
        part = seg.loc[names]
        add(f"seg_{key}_customers", int(part["customers"].sum()), "customers", "rfm_segments.csv", "sum")
        add(f"seg_{key}_customers_pct", round(part["pct_of_customers"].sum(), 2), "%", "rfm_segments.csv", "sum")
        add(f"seg_{key}_revenue_gbp", round(part["revenue_gbp"].sum(), 2), "GBP", "rfm_segments.csv", "sum")
        add(f"seg_{key}_revenue_pct", round(part["pct_of_revenue"].sum(), 2), "%", "rfm_segments.csv", "sum")

    # ---------------------------------------------------------------- products & countries
    pareto = load("pareto_summary").set_index("measure")
    add("products", int(load("product_pareto")["revenue_rank"].max()), "products", "product_pareto.csv", "")
    add("top_20pct_products_revenue_pct", pareto.loc["top 20% of products", "pct_of_revenue"], "%",
        "pareto_summary.csv", "")
    add("products_for_half_of_revenue", int(pareto.loc["products needed for 50% of revenue", "products"]),
        "products", "pareto_summary.csv", "")
    add("products_for_half_of_revenue_pct", pareto.loc["products needed for 50% of revenue",
                                                       "pct_of_products"], "%", "pareto_summary.csv", "")
    add("bottom_50pct_products_revenue_pct",
        round(100 - pareto.loc["top 50% of products", "pct_of_revenue"], 2), "%", "pareto_summary.csv",
        "100 - top 50% share")
    countries = load("country_revenue").set_index("country")
    add("countries", len(countries), "countries", "country_revenue.csv", "incl. 'Unspecified'")
    add("uk_revenue_pct", countries.loc["United Kingdom", "pct_of_revenue"], "%", "country_revenue.csv", "")
    non_uk = countries.drop(index="United Kingdom")
    top2 = non_uk.head(2)
    add("top_2_export_markets", " & ".join(top2.index), "", "country_revenue.csv", "by revenue")
    add("top_2_export_markets_pct_of_non_uk", round(top2["pct_of_non_uk_revenue"].sum(), 2), "%",
        "country_revenue.csv", "")
    add("top_2_export_markets_customers", int(top2["customers"].sum()), "customers", "country_revenue.csv", "")

    out = pd.DataFrame(rows)
    out.to_csv(R / "key_metrics.csv", index=False)
    print(f"  wrote results/key_metrics.csv ({len(out)} metrics)")
    return out


def as_dict() -> dict:
    """Key metrics as {metric: value}, numbers converted back from text."""
    df = pd.read_csv(R / "key_metrics.csv", dtype={"value": str})
    out = {}
    for metric, value in zip(df["metric"], df["value"]):
        try:
            out[metric] = float(value)
        except ValueError:
            out[metric] = value
    return out


if __name__ == "__main__":
    compute()
