-- Revenue by country (the country recorded on each order line).
--   * Revenue and orders include lines with no Customer ID (shown separately);
--     customers counts identified customers (a few customers ordered from two
--     countries and count in both).
--   * "EIRE" is the Republic of Ireland, as recorded in the source.
WITH by_country AS (
    SELECT
        country,
        SUM(revenue)                AS revenue_gbp,
        COALESCE(SUM(revenue) FILTER (WHERE customer_id IS NULL), 0) AS revenue_no_customer_id_gbp,
        COUNT(DISTINCT invoice)     AS orders,
        COUNT(DISTINCT customer_id) AS customers
    FROM sales
    GROUP BY country
)
SELECT
    RANK() OVER (ORDER BY revenue_gbp DESC)                        AS revenue_rank,
    country,
    ROUND(revenue_gbp, 2)                                          AS revenue_gbp,
    ROUND(100.0 * revenue_gbp / SUM(revenue_gbp) OVER (), 2)       AS pct_of_revenue,
    -- share of all revenue earned outside the UK (NULL for the UK itself)
    CASE WHEN country <> 'United Kingdom' THEN
        ROUND(100.0 * revenue_gbp / SUM(revenue_gbp) FILTER (WHERE country <> 'United Kingdom') OVER (), 2)
    END                                                            AS pct_of_non_uk_revenue,
    ROUND(revenue_no_customer_id_gbp, 2)                           AS revenue_no_customer_id_gbp,
    orders,
    customers,
    ROUND(revenue_gbp / orders, 2)                                 AS avg_order_value_gbp
FROM by_country
ORDER BY revenue_gbp DESC, country;
