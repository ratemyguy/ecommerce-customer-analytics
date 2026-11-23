-- How soon do new customers come back? For customers whose first purchase leaves a
-- full 365 days of follow-up in the data, the cumulative share that made a second
-- purchase within N days (N = 1..365).
--   * A "second purchase" is an order on a later calendar day than the first one
--     (several invoices on the first day count as one visit).
--   * Excludes the first month of data (December 2009): those "first" purchases are
--     often established customers (left-censoring).
--   * Requiring 365 days of follow-up avoids counting late joiners as non-returners.
WITH purchase_days AS (
    SELECT DISTINCT customer_id, invoice_date::DATE AS purchase_day
    FROM sales
    WHERE customer_id IS NOT NULL
),
numbered AS (
    SELECT customer_id, purchase_day,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY purchase_day) AS nth_day
    FROM purchase_days
),
first_second AS (
    SELECT customer_id,
           MIN(purchase_day) FILTER (WHERE nth_day = 1) AS first_day,
           MIN(purchase_day) FILTER (WHERE nth_day = 2) AS second_day
    FROM numbered
    GROUP BY customer_id
),
bounds AS (
    SELECT date_trunc('month', MIN(invoice_date))::DATE + INTERVAL 1 MONTH AS first_eligible_day,
           MAX(invoice_date)::DATE - INTERVAL 365 DAY                    AS last_eligible_day
    FROM sales
),
eligible AS (
    SELECT f.customer_id, date_diff('day', f.first_day, f.second_day) AS days_to_second
    FROM first_second AS f
    CROSS JOIN bounds AS b
    WHERE f.first_day BETWEEN b.first_eligible_day AND b.last_eligible_day
),
returns_by_day AS (
    SELECT days_to_second AS day, COUNT(*) AS customers
    FROM eligible
    WHERE days_to_second <= 365
    GROUP BY 1
)
SELECT
    d.day                                                            AS days_since_first_purchase,
    (SELECT COUNT(*) FROM eligible)                                  AS new_customers,
    (SUM(COALESCE(r.customers, 0)) OVER (ORDER BY d.day))::BIGINT    AS returned_customers,
    ROUND(100.0 * SUM(COALESCE(r.customers, 0)) OVER (ORDER BY d.day)
          / (SELECT COUNT(*) FROM eligible), 2)                      AS pct_returned
FROM (SELECT range AS day FROM range(1, 366)) AS d
LEFT JOIN returns_by_day AS r USING (day)
ORDER BY d.day;
