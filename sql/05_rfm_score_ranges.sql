-- What each RFM score means in plain units: for every score 1-5, how many customers
-- got it and the range of recency days / orders / revenue behind it.
-- Uses the rfm_customers result (04_rfm_customers.sql).
WITH r AS (
    SELECT r_score AS score, COUNT(*) AS r_customers,
           MIN(recency_days) AS r_min_days, MAX(recency_days) AS r_max_days
    FROM rfm_customers GROUP BY 1
),
f AS (
    SELECT f_score AS score, COUNT(*) AS f_customers,
           MIN(frequency) AS f_min_orders, MAX(frequency) AS f_max_orders
    FROM rfm_customers GROUP BY 1
),
m AS (
    SELECT m_score AS score, COUNT(*) AS m_customers,
           MIN(monetary_gbp) AS m_min_gbp, MAX(monetary_gbp) AS m_max_gbp
    FROM rfm_customers GROUP BY 1
)
SELECT *
FROM (SELECT range AS score FROM range(1, 6)) AS s
LEFT JOIN r USING (score)
LEFT JOIN f USING (score)
LEFT JOIN m USING (score)
ORDER BY score;
