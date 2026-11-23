-- RFM scores and segment for every identified customer.
--   Recency   = days from the customer's last purchase to the snapshot date
--               (the day after the last invoice in the data, 2011-12-10).
--   Frequency = number of orders (distinct invoices) over the whole period.
--   Monetary  = product revenue in GBP over the whole period.
-- Each is scored 1-5 with NTILE(5); 5 is best (most recent, most orders, most spend).
-- NTILE alone splits tied values across buckets arbitrarily - e.g. thousands of
-- customers with exactly one order would land in buckets 1 AND 2. So every customer
-- with the same value gets the same score: the lowest bucket that value reached
-- (MIN(...) OVER (PARTITION BY value)). Score groups are therefore not exactly 20%
-- each; see results/rfm_score_ranges.csv.
-- Segment rules are evaluated top to bottom (first match wins) and are listed in the
-- README and in src/segments.py, which re-checks this CASE independently.
WITH customer_country AS (     -- a few customers ordered from 2 countries: keep the most frequent
    SELECT customer_id, country
    FROM sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id, country
    QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY COUNT(*) DESC, country) = 1
),
customer AS (
    SELECT
        customer_id,
        MIN(invoice_date)::DATE  AS first_purchase,
        MAX(invoice_date)::DATE  AS last_purchase,
        COUNT(DISTINCT invoice)  AS frequency,
        SUM(revenue)             AS monetary_gbp
    FROM sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
snapshot AS (
    SELECT MAX(invoice_date)::DATE + 1 AS snapshot_date FROM sales
),
base AS (
    SELECT c.*, date_diff('day', c.last_purchase, s.snapshot_date) AS recency_days
    FROM customer AS c
    CROSS JOIN snapshot AS s
),
tiles AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC, customer_id) AS r_tile,  -- long ago -> 1
        NTILE(5) OVER (ORDER BY frequency, customer_id)         AS f_tile,  -- few orders -> 1
        NTILE(5) OVER (ORDER BY monetary_gbp, customer_id)      AS m_tile   -- low spend -> 1
    FROM base
),
scored AS (
    SELECT
        *,
        MIN(r_tile) OVER (PARTITION BY recency_days) AS r_score,
        MIN(f_tile) OVER (PARTITION BY frequency)    AS f_score,
        MIN(m_tile) OVER (PARTITION BY monetary_gbp) AS m_score
    FROM tiles
)
SELECT
    s.customer_id,
    cc.country,
    s.first_purchase,
    s.last_purchase,
    s.recency_days,
    s.frequency,
    ROUND(s.monetary_gbp, 2)                                   AS monetary_gbp,
    s.r_score,
    s.f_score,
    s.m_score,
    s.r_score::VARCHAR || s.f_score::VARCHAR || s.m_score::VARCHAR AS rfm_cell,
    CASE
        WHEN s.r_score >= 4 AND s.f_score >= 4 AND s.m_score >= 4 THEN 'Champions'
        WHEN s.r_score <= 2 AND s.f_score >= 4 AND s.m_score >= 4 THEN 'Can''t Lose'
        WHEN s.r_score <= 2 AND s.f_score >= 3                    THEN 'At Risk'
        WHEN s.r_score >= 3 AND s.f_score >= 3                    THEN 'Loyal'
        WHEN s.r_score >= 4 AND s.f_score  = 2                    THEN 'Potential Loyalists'
        WHEN s.r_score >= 4 AND s.f_score  = 1                    THEN 'New'
        WHEN s.r_score >= 2                                       THEN 'Hibernating'  -- R 2-3, F 1-2
        ELSE                                                           'Lost'         -- R 1,   F 1-2
    END                                                        AS segment
FROM scored AS s
JOIN customer_country AS cc USING (customer_id)
ORDER BY s.monetary_gbp DESC, s.customer_id;
