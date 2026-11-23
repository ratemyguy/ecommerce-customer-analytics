"""RFM segment definitions: names, rules, plain-English meaning and a 1-line action.

The SQL CASE in sql/04_rfm_customers.sql assigns the segments. This module holds the
human-readable version used by the README, the CSV outputs and the Excel report, and
`verify()` re-implements the same rules in pandas to prove the two agree for every
customer.

Scores run 1-5 (5 = most recent / most orders / most spend). Rules are checked top
to bottom and the first match wins, which makes the eight segments cover all 125
R-F-M combinations with no overlap.
"""
import pandas as pd

SEGMENTS = [
    {
        "segment": "Champions",
        "rule": "R >= 4 and F >= 4 and M >= 4",
        "test": lambda r, f, m: r >= 4 and f >= 4 and m >= 4,
        "meaning": "Bought recently, order often and spend the most.",
        "action": "Protect: account contact, early access to the autumn range; no blanket discounts.",
    },
    {
        "segment": "Can't Lose",
        "rule": "R <= 2 and F >= 4 and M >= 4",
        "test": lambda r, f, m: r <= 2 and f >= 4 and m >= 4,
        "meaning": "Used to order often and spend a lot, but not for months.",
        "action": "Personal win-back call or email before the next peak; ask why they stopped.",
    },
    {
        "segment": "At Risk",
        "rule": "R <= 2 and F >= 3 (not Can't Lose)",
        "test": lambda r, f, m: r <= 2 and f >= 3,
        "meaning": "Regular buyers who have gone quiet.",
        "action": "Win-back emails featuring products they bought before, with a time limit.",
    },
    {
        "segment": "Loyal",
        "rule": "R >= 3 and F >= 3 (not Champions)",
        "test": lambda r, f, m: r >= 3 and f >= 3,
        "meaning": "Order regularly and fairly recently.",
        "action": "Cross-sell best-sellers they have not tried; reorder reminders.",
    },
    {
        "segment": "Potential Loyalists",
        "rule": "R >= 4 and F = 2",
        "test": lambda r, f, m: r >= 4 and f == 2,
        "meaning": "Recent customers on their second order.",
        "action": "Push for the third order: reorder reminder and a bundle offer.",
    },
    {
        "segment": "New",
        "rule": "R >= 4 and F = 1",
        "test": lambda r, f, m: r >= 4 and f == 1,
        "meaning": "First and only order was recent.",
        "action": "Welcome series that asks for a second order within the first few weeks.",
    },
    {
        "segment": "Hibernating",
        "rule": "R = 2 or 3 and F <= 2",
        "test": lambda r, f, m: r >= 2,
        "meaning": "One or two orders, a few months ago.",
        "action": "Low-cost reactivation only in the seasonal (Sep-Nov) campaign.",
    },
    {
        "segment": "Lost",
        "rule": "R = 1 and F <= 2",
        "test": lambda r, f, m: True,
        "meaning": "One or two orders, long ago.",
        "action": "Keep out of paid campaigns; cheap bulk email at most.",
    },
]


def definitions_frame() -> pd.DataFrame:
    """Segment order, rule, meaning and action - registered in DuckDB for 06_rfm_segments.sql."""
    return pd.DataFrame(
        [{"segment_order": i + 1, **{k: v for k, v in s.items() if k != "test"}}
         for i, s in enumerate(SEGMENTS)]
    )


def assign(r: int, f: int, m: int) -> str:
    """Python version of the SQL CASE: the first rule that matches wins."""
    for s in SEGMENTS:
        if s["test"](r, f, m):
            return s["segment"]
    raise AssertionError("rules must cover every score combination")


def verify(rfm: pd.DataFrame) -> None:
    """Check the SQL segment of every customer against the Python rules."""
    python_segment = [assign(r, f, m) for r, f, m in
                      zip(rfm["r_score"], rfm["f_score"], rfm["m_score"])]
    mismatches = (rfm["segment"] != pd.Series(python_segment, index=rfm.index)).sum()
    if mismatches:
        raise AssertionError(f"{mismatches} customers have a different segment in SQL and Python")
    # Every one of the 125 score combinations maps to exactly one known segment.
    names = {s["segment"] for s in SEGMENTS}
    assert all(assign(r, f, m) in names
               for r in range(1, 6) for f in range(1, 6) for m in range(1, 6))
    print(f"  segments: SQL and Python rules agree for all {len(rfm):,} customers")
