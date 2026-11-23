-- Segment summary: size, revenue share and simple historical value per segment.
-- "Revenue per customer" is what customers in the segment actually spent over the
-- observed period (Dec 2009 - Dec 2011); it is descriptive, not a forecast.
-- Uses rfm_customers (04) and segment_definitions (order, rule and action text,
-- registered from src/segments.py).
WITH seg AS (
    SELECT
        segment,
        COUNT(*)                     AS customers,
        SUM(monetary_gbp)            AS revenue_gbp,
        AVG(monetary_gbp)            AS avg_revenue_per_customer_gbp,
        MEDIAN(monetary_gbp)         AS median_revenue_per_customer_gbp,
        AVG(frequency)               AS avg_orders,
        MEDIAN(recency_days)         AS median_days_since_last_order
    FROM rfm_customers
    GROUP BY segment
)
SELECT
    d.segment_order,
    s.segment,
    d.rule,
    s.customers,
    ROUND(100.0 * s.customers / SUM(s.customers) OVER (), 2)     AS pct_of_customers,
    ROUND(s.revenue_gbp, 2)                                      AS revenue_gbp,
    ROUND(100.0 * s.revenue_gbp / SUM(s.revenue_gbp) OVER (), 2) AS pct_of_revenue,
    ROUND(s.avg_revenue_per_customer_gbp, 2)                     AS avg_revenue_per_customer_gbp,
    ROUND(s.median_revenue_per_customer_gbp, 2)                  AS median_revenue_per_customer_gbp,
    ROUND(s.avg_orders, 1)                                       AS avg_orders,
    s.median_days_since_last_order,
    d.action
FROM seg AS s
JOIN segment_definitions AS d USING (segment)
ORDER BY d.segment_order;
