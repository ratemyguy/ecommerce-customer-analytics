"""Step 6 - draw the README charts (matplotlib, PNG, 1200x700 px at 150 dpi).

Every chart reads a CSV from results/, and every number in a title is taken from
results/key_metrics.csv, so the titles cannot drift from the data.

Run:  python -I src/charts.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only, no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import metrics  # noqa: E402

NAVY, GRAY = config.NAVY, config.GRAY       # palette: see config.py
INK, MUTED, GRID = "#1B1F24", "#5B6573", "#E3E6EA"   # text, secondary text, hairlines
R = config.RESULTS_DIR

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": "#C3C8CF",
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def figure(title: str, subtitle: str, **adjust):
    """A 1200x700 px figure with a left-aligned takeaway title and a grey subtitle."""
    fig, ax = plt.subplots(figsize=(8, 7 / 1.5), dpi=150)
    fit_width(fig, fig.text(0.015, 0.965, title, fontsize=12.5, fontweight="bold", color=INK, va="top"))
    fit_width(fig, fig.text(0.015, 0.905, subtitle, fontsize=8.5, color=MUTED, va="top"))
    margins = {"left": 0.09, "right": 0.97, "top": 0.82, "bottom": 0.13}
    margins.update(adjust)
    fig.subplots_adjust(**margins)
    return fig, ax


def fit_width(fig, text, max_share=0.97, min_size=7.0):
    """Shrink a text's font until it fits inside the figure width (no clipped titles)."""
    renderer = fig.canvas.get_renderer()
    while text.get_window_extent(renderer).x1 > fig.bbox.width * max_share:
        if text.get_fontsize() <= min_size:
            raise ValueError(f"text too long for the chart: {text.get_text()!r}")
        text.set_fontsize(text.get_fontsize() - 0.25)


def finish(fig, name: str, note: str = "") -> None:
    text = config.SOURCE_NOTE + (f". {note}" if note else "")
    fit_width(fig, fig.text(0.015, 0.018, text, fontsize=6.8, color=MUTED, va="bottom"), min_size=5.5)
    config.IMAGES_DIR.mkdir(exist_ok=True)
    fig.savefig(config.IMAGES_DIR / name, dpi=150)
    plt.close(fig)
    print(f"  images/{name}")


def value_grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def pct(x, digits=0):
    return f"{x:.{digits}f}%"


def gbp_short(x):
    return f"£{x / 1e6:.2f}M" if x >= 1e6 else f"£{x / 1e3:,.0f}k"


# ------------------------------------------------------------------ 1. monthly revenue
def monthly_revenue(k):
    m = pd.read_csv(R / "monthly_kpis.csv", parse_dates=["month"])
    autumn = m["month"].dt.month.isin([9, 10, 11])
    colors = np.where(autumn, NAVY, GRAY)
    fig, ax = figure(
        f"Revenue is flat year on year; September-November bring {pct(k['sep_nov_share_of_12_months_pct'])} of it",
        f"Monthly product revenue. Jan-Nov 2011 was {k['revenue_growth_jan_nov_pct']:+.1f}% on Jan-Nov 2010; "
        f"the peak month ({k['peak_month']}) was {k['peak_to_lowest_ratio']:.1f}x the slowest ({k['lowest_month']}).")
    x = np.arange(len(m))
    full = ~m["is_partial_month"]
    ax.bar(x[full], m.loc[full, "revenue_gbp"] / 1e3, width=0.62, color=colors[full], zorder=2)
    ax.bar(x[~full], m.loc[~full, "revenue_gbp"] / 1e3, width=0.62, color="white",
           edgecolor=GRAY, hatch="////", linewidth=0.8, zorder=2)
    for i in m.index[m["month"].dt.month == 11]:
        ax.annotate(gbp_short(m.loc[i, "revenue_gbp"]), (x[i], m.loc[i, "revenue_gbp"] / 1e3),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, color=INK)
    last = m.index[~full][0]
    ax.annotate("1-9 Dec\nonly", (x[last], m.loc[last, "revenue_gbp"] / 1e3), xytext=(0, 3),
                textcoords="offset points", ha="center", fontsize=7.5, color=MUTED)
    ticks = [i for i in x if m.loc[i, "month"].month in (12, 3, 6, 9)]
    ax.set_xticks(ticks, [m.loc[i, "month"].strftime("%b\n%Y") for i in ticks])
    ax.set_xlim(-0.7, len(m) - 0.3)
    ax.set_ylabel("Revenue (£ thousands)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylim(0, m["revenue_gbp"].max() / 1e3 * 1.12)
    value_grid(ax)
    ax.legend(handles=[Patch(color=NAVY, label="September-November"), Patch(color=GRAY, label="Other months"),
                       Patch(facecolor="white", edgecolor=GRAY, hatch="////", label="Partial month")],
              loc="upper left", frameon=False, fontsize=8)
    finish(fig, "monthly_revenue.png", "Revenue = quantity x unit price of product lines after cleaning")


# ------------------------------------------------------------------ 2. cohort heatmap
def cohort_heatmap(k):
    c = pd.read_csv(R / "cohort_retention.csv", parse_dates=["cohort_month"])
    c = c[(c["months_since_first"].between(1, 12)) & (~c["activity_month_is_partial"])]
    sizes = (pd.read_csv(R / "cohort_retention.csv", parse_dates=["cohort_month"])
             .query("months_since_first == 0").set_index("cohort_month")["cohort_size"])
    last_full = pd.Timestamp(
        pd.read_csv(R / "monthly_kpis.csv", parse_dates=["month"]).query("~is_partial_month")["month"].max())
    sizes = sizes[sizes.index < last_full]                  # cohorts with at least one full later month
    grid = (c.pivot(index="cohort_month", columns="months_since_first", values="retention_pct")
            .reindex(index=sizes.index, columns=range(1, 13)))
    # A cell is "observed" when the whole activity month is inside the data.
    for cohort in grid.index:
        for kk in grid.columns:
            if cohort + pd.DateOffset(months=kk) > last_full:
                grid.loc[cohort, kk] = np.nan
            elif pd.isna(grid.loc[cohort, kk]):
                grid.loc[cohort, kk] = 0.0                  # observed, nobody came back
    fig, ax = figure(
        f"About 1 in 5 new customers orders again the next month ({pct(k['retention_month_1_pct'])})",
        f"% of each first-purchase cohort ordering in a later month. Pooled: {k['retention_month_11_pct']:.0f}% "
        f"in month 11, {k['retention_month_12_pct']:.0f}% in month 12 (the next gift season).",
        left=0.14, right=0.93, bottom=0.12, top=0.84)
    cmap = LinearSegmentedColormap.from_list("navy", ["#F4F6F9", "#9FB0C7", NAVY])
    vmax = 5 * np.ceil(np.nanmax(grid.values) / 5)
    img = ax.imshow(grid.values, aspect="auto", cmap=cmap, vmin=0, vmax=vmax, interpolation="nearest")
    for (i, j), v in np.ndenumerate(grid.values):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.3,
                    color="white" if v > vmax * 0.55 else INK)
    labels = [f"{d:%b %Y}{'*' if n == 0 else ''}  (n={sizes.iloc[n]:,})" for n, d in enumerate(grid.index)]
    ax.set_yticks(range(len(grid)), labels, fontsize=6.6)
    ax.set_xticks(range(12), [str(i) for i in range(1, 13)])
    ax.set_xlabel("Months after first purchase")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    bar = fig.colorbar(img, ax=ax, fraction=0.03, pad=0.02)
    bar.set_label("% of cohort ordering", color=MUTED, fontsize=7.5)
    bar.ax.tick_params(labelsize=7, colors=MUTED)
    bar.outline.set_visible(False)
    finish(fig, "cohort_retention_heatmap.png",
           "*Dec 2009 also holds established customers (data starts Dec 2009). Blank = not observed yet")


# ------------------------------------------------------------------ 3. segments
def segments_chart(k):
    s = pd.read_csv(R / "rfm_segments.csv").sort_values("pct_of_revenue")
    champions = s.set_index("segment").loc["Champions"]
    fig, ax = figure(
        f"Champions are {pct(champions['pct_of_customers'])} of customers but bring in "
        f"{pct(champions['pct_of_revenue'])} of revenue",
        f"Share of identified customers and of their revenue by RFM segment, Dec 2009-Dec 2011 "
        f"({int(k['customers_identified']):,} customers)", left=0.17, right=0.95)
    y = np.arange(len(s))
    h = 0.36
    ax.barh(y + h / 2, s["pct_of_customers"], height=h, color=GRAY, label="% of customers", zorder=2)
    ax.barh(y - h / 2, s["pct_of_revenue"], height=h, color=NAVY, label="% of revenue", zorder=2)
    for yy, v in zip(y + h / 2, s["pct_of_customers"]):
        ax.text(v + 0.8, yy, pct(v), va="center", fontsize=7.5, color=MUTED)
    for yy, v in zip(y - h / 2, s["pct_of_revenue"]):
        ax.text(v + 0.8, yy, pct(v, 1 if v < 1 else 0), va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, s["segment"])
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Share (%)")
    ax.set_xlim(0, 78)
    value_grid(ax, "x")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    finish(fig, "segments_customers_vs_revenue.png", "Segment rules: see README")


# ------------------------------------------------------------------ 4. Pareto
def pareto_chart(k):
    p = pd.read_csv(R / "product_pareto.csv")
    x = np.concatenate([[0], p["cumulative_pct_of_products"]])
    y = np.concatenate([[0], p["cumulative_pct_of_revenue"]])
    fig, ax = figure(
        f"The top 20% of products earn {pct(k['top_20pct_products_revenue_pct'])} of product revenue",
        f"Cumulative share of revenue, products ranked from best-selling ({int(k['products']):,} products). "
        f"The bottom half of the range earns {pct(k['bottom_50pct_products_revenue_pct'], 1)}.")
    ax.plot([0, 100], [0, 100], color=GRAY, linewidth=1, zorder=1)
    ax.text(62, 56, "if every product sold the same", color=MUTED, fontsize=7.5, rotation=0)
    ax.plot(x, y, color=NAVY, linewidth=2, solid_capstyle="round", zorder=2)
    pts = [(20.0, k["top_20pct_products_revenue_pct"],
            f"Top 20% of products:\n{pct(k['top_20pct_products_revenue_pct'])} of revenue", (14, -34)),
           (k["products_for_half_of_revenue_pct"], 50.0,
            f"{int(k['products_for_half_of_revenue'])} products "
            f"({pct(k['products_for_half_of_revenue_pct'])}):\nhalf of revenue", (16, -24))]
    for px, py, label, offset in pts:
        ax.plot(px, py, "o", color=NAVY, markersize=6.5, markeredgecolor="white", markeredgewidth=1.5, zorder=3)
        ax.annotate(label, (px, py), xytext=offset, textcoords="offset points", fontsize=8, color=INK,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.7})
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Cumulative % of products (best-selling first)")
    ax.set_ylabel("Cumulative % of revenue")
    value_grid(ax, "both")
    finish(fig, "product_pareto.png", "Product = stock code")


# ------------------------------------------------------------------ 5. countries
def countries_chart(k):
    c = pd.read_csv(R / "country_revenue.csv")
    top = c[c["country"] != "United Kingdom"].head(10).iloc[::-1]
    names = top["country"].replace({"EIRE": "Ireland (EIRE)"})
    fig, ax = figure(
        f"Ireland and the Netherlands bring {pct(k['top_2_export_markets_pct_of_non_uk'])} of non-UK revenue",
        f"The UK is {pct(k['uk_revenue_pct'])} of all revenue. Top 10 other countries by revenue; "
        "labels show revenue and identified customers.",
        left=0.17, right=0.93)
    y = np.arange(len(top))
    ax.barh(y, top["revenue_gbp"] / 1e3, height=0.58, color=NAVY, zorder=2)
    for yy, (rev, cust) in zip(y, zip(top["revenue_gbp"], top["customers"])):
        ax.text(rev / 1e3 + 8, yy, f"£{rev / 1e3:,.0f}k · {cust} customer{'s' if cust != 1 else ''}",
                va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, names)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Revenue (£ thousands)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlim(0, top["revenue_gbp"].max() / 1e3 * 1.32)
    value_grid(ax, "x")
    finish(fig, "top_countries_ex_uk.png", "Country as recorded on each order line")


# ------------------------------------------------------------------ 6. time to 2nd order
def repeat_timing_chart(k):
    t = pd.read_csv(R / "repeat_purchase_timing.csv")
    fig, ax = figure(
        f"Only {pct(k['reordered_within_30d_pct'])} of new customers reorder within 30 days; "
        f"{pct(k['reordered_within_365d_pct'])} do within a year",
        f"Cumulative % with a second order. New customers of Jan-9 Dec 2010 "
        f"(n = {int(k['new_customers_with_1y_followup']):,}), each followed for a full year.")
    x = np.concatenate([[0], t["days_since_first_purchase"]])
    y = np.concatenate([[0], t["pct_returned"]])
    ax.fill_between(x, y, color=NAVY, alpha=0.08, linewidth=0)
    ax.plot(x, y, color=NAVY, linewidth=2, zorder=2)
    for d, offset in ((30, (8, -4)), (90, (8, -8)), (365, (-6, -24))):
        v = t.loc[t["days_since_first_purchase"] == d, "pct_returned"].iat[0]
        ax.plot(d, v, "o", color=NAVY, markersize=6.5, markeredgecolor="white", markeredgewidth=1.5, zorder=3)
        ax.annotate(f"{pct(v)} by day {d}", (d, v), xytext=offset, textcoords="offset points",
                    fontsize=8, color=INK, ha="right" if d == 365 else "left")
    med = k["median_days_to_second_order_returners"]
    ax.axvline(med, color=GRAY, linewidth=1, zorder=1)
    ax.text(med + 4, 5, f"half of those who come back\ndo so within {int(med)} days", fontsize=7.5, color=MUTED)
    ax.set_xlim(0, 372)
    ax.set_ylim(0, 80)
    ax.set_xticks([0, 30, 60, 90, 120, 180, 240, 300, 365])
    ax.set_xlabel("Days since first purchase")
    ax.set_ylabel("% with a second order")
    value_grid(ax)
    finish(fig, "days_to_second_order.png", "A second order = a purchase on a later day")


def make_charts():
    k = metrics.as_dict()
    monthly_revenue(k)
    cohort_heatmap(k)
    segments_chart(k)
    pareto_chart(k)
    countries_chart(k)
    repeat_timing_chart(k)


if __name__ == "__main__":
    make_charts()
