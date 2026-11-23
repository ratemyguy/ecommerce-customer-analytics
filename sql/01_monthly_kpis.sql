-- Monthly KPIs: revenue, orders, active and new customers, average order value,
-- and the product cancellation rate.
--   * Revenue and orders include lines with no Customer ID (guest orders);
--     customer counts use identified customers only (COUNT DISTINCT skips NULLs).
--   * Cancellation rate = value of product cancellations / value of product sales
--     in the same month. Same-day keying-error voids are excluded from both sides
--     (see results/data_quality.csv).
--   * Revenue is split by who bought: new customers (first month in the data),
--     returning customers (bought in an earlier month) and lines with no Customer ID.
--     Because the data starts in Dec 2009, some "new" customers in early 2010 were
--     really established ones, so the returning share is if anything understated.
--   * The data ends on 2011-12-09, so December 2011 is flagged as a partial month.
WITH first_purchase AS (       -- each identified customer's first month in the data
    SELECT customer_id, date_trunc('month', MIN(invoice_date))::DATE AS first_month
    FROM sales
    WHERE customer_id IS NOT NULL
    GROUP BY 1
),
sales_by_month AS (
    SELECT
        date_trunc('month', s.invoice_date)::DATE                      AS month,
        SUM(s.revenue)                                                 AS revenue_gbp,
        COUNT(DISTINCT s.invoice)                                      AS orders,
        COUNT(DISTINCT s.customer_id)                                  AS active_customers,
        SUM(s.revenue) FILTER (WHERE f.first_month = date_trunc('month', s.invoice_date))
                                                                       AS revenue_new_customers_gbp,
        SUM(s.revenue) FILTER (WHERE f.first_month < date_trunc('month', s.invoice_date))
                                                                       AS revenue_returning_customers_gbp,
        SUM(s.revenue) FILTER (WHERE s.customer_id IS NULL)            AS revenue_no_customer_id_gbp,
        MAX(s.invoice_date)::DATE                                      AS last_day_with_data
    FROM sales AS s
    LEFT JOIN first_purchase AS f USING (customer_id)
    GROUP BY 1
),
new_customers AS (
    SELECT first_month AS month, COUNT(*) AS new_customers
    FROM first_purchase
    GROUP BY 1
),
product_cancellations AS (
    SELECT
        date_trunc('month', invoice_date)::DATE AS month,
        -SUM(value)                             AS cancelled_value_gbp,
        COUNT(DISTINCT invoice)                 AS cancellation_invoices
    FROM cancellations
    WHERE is_product AND NOT voided_within_24h
    GROUP BY 1
)
SELECT
    s.month,
    ROUND(s.revenue_gbp, 2)                                   AS revenue_gbp,
    s.orders,
    s.active_customers,
    n.new_customers,
    s.active_customers - n.new_customers                      AS returning_customers,
    ROUND(s.revenue_gbp / s.orders, 2)                        AS avg_order_value_gbp,
    ROUND(c.cancelled_value_gbp, 2)                           AS cancelled_value_gbp,
    ROUND(100 * c.cancelled_value_gbp / s.revenue_gbp, 2)     AS cancellation_rate_pct,
    c.cancellation_invoices,
    ROUND(COALESCE(s.revenue_new_customers_gbp, 0), 2)        AS revenue_new_customers_gbp,
    ROUND(COALESCE(s.revenue_returning_customers_gbp, 0), 2)  AS revenue_returning_customers_gbp,
    ROUND(COALESCE(s.revenue_no_customer_id_gbp, 0), 2)       AS revenue_no_customer_id_gbp,
    s.last_day_with_data,
    -- partial = the data stops before the month ends (only the final month)
    s.month = MAX(s.month) OVER ()
        AND s.last_day_with_data < last_day(s.month)           AS is_partial_month
FROM sales_by_month AS s
LEFT JOIN new_customers         AS n USING (month)
LEFT JOIN product_cancellations AS c USING (month)
ORDER BY s.month;
