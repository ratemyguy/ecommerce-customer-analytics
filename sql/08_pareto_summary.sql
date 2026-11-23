-- Pareto summary: the share of product revenue earned by the top 1/5/10/20/50% of
-- products, and how many products it takes to reach 50% and 80% of revenue.
-- Uses the product_pareto result (07_product_pareto.sql).
WITH n AS (
    SELECT COUNT(*) AS n_products FROM product_pareto
),
top_shares AS (
    SELECT
        'top ' || CAST(t.top_pct AS VARCHAR) || '% of products'   AS measure,
        CAST(CEIL(t.top_pct / 100.0 * n.n_products) AS INTEGER)   AS products,
        p.cumulative_pct_of_revenue                               AS pct_of_revenue
    FROM (VALUES (1), (5), (10), (20), (50)) AS t(top_pct)
    CROSS JOIN n
    JOIN product_pareto AS p
      ON p.revenue_rank = CAST(CEIL(t.top_pct / 100.0 * n.n_products) AS INTEGER)
),
reach AS (                     -- smallest number of products reaching each revenue share
    SELECT
        'products needed for ' || CAST(t.target AS VARCHAR) || '% of revenue' AS measure,
        MIN(p.revenue_rank)                                                   AS products,
        t.target                                                              AS pct_of_revenue
    FROM (VALUES (50), (80)) AS t(target)
    JOIN product_pareto AS p ON p.cumulative_pct_of_revenue >= t.target
    GROUP BY t.target
)
SELECT measure, products, ROUND(100.0 * products / n.n_products, 2) AS pct_of_products, pct_of_revenue
FROM (SELECT * FROM top_shares UNION ALL SELECT * FROM reach) AS x
CROSS JOIN n
ORDER BY measure LIKE 'products%', products;
