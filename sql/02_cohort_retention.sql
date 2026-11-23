-- Cohort retention: identified customers are grouped by the month of their first
-- purchase (the cohort). For every later month we count how many of them bought
-- again, as a count and as a share of the cohort.
--   * months_since_first = 0 is the first-purchase month (always 100%).
--   * Caveat: the data starts on 2009-12-01, so the December 2009 cohort also holds
--     every established customer who happened to buy that month (left-censoring).
--   * Activity in December 2011 covers only 1-9 December (flagged as partial).
WITH customer_months AS (      -- one row per customer per month with a purchase
    SELECT DISTINCT
        customer_id,
        date_trunc('month', invoice_date)::DATE AS activity_month
    FROM sales
    WHERE customer_id IS NOT NULL
),
cohorts AS (                   -- first month with a purchase = cohort
    SELECT customer_id, MIN(activity_month) AS cohort_month
    FROM customer_months
    GROUP BY 1
),
activity AS (
    SELECT
        c.cohort_month,
        date_diff('month', c.cohort_month, m.activity_month) AS months_since_first,
        m.activity_month,
        COUNT(*)                                              AS active_customers
    FROM customer_months AS m
    JOIN cohorts         AS c USING (customer_id)
    GROUP BY 1, 2, 3
),
data_end AS (
    SELECT MAX(invoice_date)::DATE AS last_day FROM sales
)
SELECT
    a.cohort_month,
    a.months_since_first,
    a.activity_month,
    a.active_customers,
    -- the month-0 count is the cohort size; window over each cohort's rows
    FIRST_VALUE(a.active_customers) OVER (
        PARTITION BY a.cohort_month ORDER BY a.months_since_first)  AS cohort_size,
    ROUND(100.0 * a.active_customers / FIRST_VALUE(a.active_customers) OVER (
        PARTITION BY a.cohort_month ORDER BY a.months_since_first), 2) AS retention_pct,
    a.activity_month = date_trunc('month', d.last_day)
        AND d.last_day < last_day(a.activity_month)                 AS activity_month_is_partial
FROM activity AS a
CROSS JOIN data_end AS d
ORDER BY a.cohort_month, a.months_since_first;
