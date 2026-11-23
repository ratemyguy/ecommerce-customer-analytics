-- Historical first-year value of a new customer: product revenue from the first
-- purchase day through the following 365 days (the same window as the 365-day point
-- of 10_repeat_purchase_timing.sql), for customers with a full year of follow-up
-- (first purchase from January 2010 to 9 December 2010; December 2009 is left out
-- because many of those "new" customers were established ones).
-- This is what past customers actually spent - a benchmark, not a forecast.
-- One row per first-purchase month, plus an 'All eligible' row.
WITH firsts AS (
    SELECT customer_id, MIN(invoice_date)::DATE AS first_day
    FROM sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
bounds AS (
    SELECT date_trunc('month', MIN(invoice_date))::DATE + INTERVAL 1 MONTH AS first_eligible_day,
           MAX(invoice_date)::DATE - INTERVAL 365 DAY                    AS last_eligible_day
    FROM sales
),
eligible AS (
    SELECT f.*
    FROM firsts AS f
    CROSS JOIN bounds AS b
    WHERE f.first_day BETWEEN b.first_eligible_day AND b.last_eligible_day
),
first_year AS (
    SELECT
        e.customer_id,
        date_trunc('month', e.first_day)::DATE                                AS first_month,
        SUM(s.revenue)                                                        AS revenue_365d,
        SUM(s.revenue) FILTER (WHERE s.invoice_date::DATE = e.first_day)      AS revenue_first_day,
        COUNT(DISTINCT s.invoice_date::DATE)                                  AS purchase_days
    FROM eligible AS e
    JOIN sales AS s
      ON s.customer_id = e.customer_id
     AND s.invoice_date::DATE BETWEEN e.first_day AND e.first_day + INTERVAL 365 DAY
    GROUP BY 1, 2
)
SELECT
    COALESCE(STRFTIME(first_month, '%Y-%m'), 'All eligible')       AS first_purchase_month,
    COUNT(*)                                                        AS new_customers,
    ROUND(AVG(revenue_365d), 2)                                     AS avg_revenue_365d_gbp,
    ROUND(MEDIAN(revenue_365d), 2)                                  AS median_revenue_365d_gbp,
    ROUND(AVG(revenue_first_day), 2)                                AS avg_first_day_revenue_gbp,
    ROUND(100.0 * SUM(revenue_365d - revenue_first_day) / SUM(revenue_365d), 2)
                                                                    AS pct_of_365d_revenue_after_first_day,
    ROUND(100.0 * AVG(CASE WHEN purchase_days >= 2 THEN 1 ELSE 0 END), 2)
                                                                    AS pct_bought_again_within_365d
FROM first_year
GROUP BY ROLLUP (first_month)
ORDER BY first_month NULLS LAST;
