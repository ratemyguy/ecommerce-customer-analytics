-- Product Pareto: products ranked by revenue with running (cumulative) shares,
-- to see how much revenue the best-selling products carry.
--   * A product = a stock code. Its name is the description used most often
--     (descriptions vary slightly over time for the same code).
--   * Includes lines with no Customer ID.
WITH product AS (
    SELECT
        stock_code,
        SUM(revenue)                 AS revenue_gbp,
        SUM(quantity)::BIGINT        AS units,
        COUNT(DISTINCT invoice)      AS orders,
        COUNT(DISTINCT customer_id)  AS customers
    FROM sales
    GROUP BY stock_code
),
product_name AS (
    SELECT stock_code, description
    FROM sales
    WHERE description IS NOT NULL
    GROUP BY stock_code, description
    QUALIFY ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY COUNT(*) DESC, description) = 1
),
ranked AS (
    SELECT
        p.*,
        n.description,
        ROW_NUMBER() OVER (ORDER BY p.revenue_gbp DESC, p.stock_code)         AS revenue_rank,
        COUNT(*)          OVER ()                                              AS n_products,
        SUM(p.revenue_gbp) OVER ()                                             AS total_revenue,
        SUM(p.revenue_gbp) OVER (ORDER BY p.revenue_gbp DESC, p.stock_code
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_revenue
    FROM product AS p
    LEFT JOIN product_name AS n USING (stock_code)
)
SELECT
    revenue_rank,
    stock_code,
    description,
    ROUND(revenue_gbp, 2)                                AS revenue_gbp,
    units,
    orders,
    customers,
    ROUND(100.0 * revenue_gbp / total_revenue, 4)        AS pct_of_revenue,
    ROUND(100.0 * running_revenue / total_revenue, 4)    AS cumulative_pct_of_revenue,
    ROUND(100.0 * revenue_rank / n_products, 4)          AS cumulative_pct_of_products
FROM ranked
ORDER BY revenue_rank;
