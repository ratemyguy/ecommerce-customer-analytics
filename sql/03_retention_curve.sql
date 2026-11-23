-- Average retention curve: for each number of months after the first purchase,
-- the share of new customers who bought in that month, pooled across cohorts
-- (i.e. weighted by cohort size).
--   * Uses the cohort_retention result (02_cohort_retention.sql).
--   * Leaves out the December 2009 cohort (it mixes new and established customers)
--     and the partial month (December 2011), so every cohort in a column was
--     observed for that full month.
--   * A cohort with nobody active in a month has no row in cohort_retention,
--     so cohort sizes are taken from month 0 and joined on.
WITH cohort_sizes AS (
    SELECT cohort_month, cohort_size
    FROM cohort_retention
    WHERE months_since_first = 0
),
bounds AS (
    SELECT
        MIN(cohort_month)                                        AS first_cohort,
        MAX(activity_month) FILTER (WHERE NOT activity_month_is_partial) AS last_full_month
    FROM cohort_retention
),
grid AS (                      -- every (cohort, month offset) that was fully observed
    SELECT s.cohort_month, s.cohort_size, k.months_since_first
    FROM cohort_sizes AS s
    CROSS JOIN bounds AS b
    CROSS JOIN (SELECT range AS months_since_first FROM range(1, 25)) AS k
    WHERE s.cohort_month > b.first_cohort
      AND s.cohort_month + to_months(k.months_since_first) <= b.last_full_month
)
SELECT
    g.months_since_first,
    COUNT(*)                                                   AS cohorts_included,
    SUM(g.cohort_size)::BIGINT                                 AS customers_in_cohorts,
    SUM(COALESCE(r.active_customers, 0))::BIGINT               AS active_customers,
    ROUND(100.0 * SUM(COALESCE(r.active_customers, 0)) / SUM(g.cohort_size), 2) AS retention_pct
FROM grid AS g
LEFT JOIN cohort_retention AS r
       ON r.cohort_month = g.cohort_month
      AND r.months_since_first = g.months_since_first
GROUP BY 1
ORDER BY 1;
