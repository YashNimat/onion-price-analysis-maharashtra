-- ============================================================
-- Analysis queries. Run in DB Browser for SQLite, or via src/run_sql.py
-- Each query is separated by a "-- name:" marker so run_sql.py can find it.
-- ============================================================

-- name: data_coverage
-- Q: How much data do we have per commodity? (always show this first - it tells the reader what to trust)
SELECT commodity,
       COUNT(*)                         AS rows_,
       COUNT(DISTINCT market)           AS markets,
       MIN(price_date)                  AS first_date,
       MAX(price_date)                  AS last_date,
       COUNT(DISTINCT price_date)       AS days_with_data
FROM fact_prices
GROUP BY commodity
ORDER BY rows_ DESC;

-- name: monthly_price_yoy
-- Q: How do monthly average prices compare with the same month last year?
WITH monthly AS (
    SELECT commodity,
           SUBSTR(price_date, 1, 7) AS ym,
           CAST(SUBSTR(price_date, 6, 2) AS INTEGER) AS month_no,
           AVG(modal_price) AS avg_price
    FROM fact_prices WHERE is_outlier = 0
    GROUP BY commodity, ym
)
SELECT commodity, ym, ROUND(avg_price, 0) AS avg_price,
       ROUND(100.0 * (avg_price - LAG(avg_price, 12) OVER (PARTITION BY commodity ORDER BY ym))
             / LAG(avg_price, 12) OVER (PARTITION BY commodity ORDER BY ym), 1) AS yoy_pct
FROM monthly
ORDER BY commodity, ym;

-- name: seasonal_index_by_month
-- Q: Which calendar months are structurally high / low priced?
--    index = month average / that year's average  (so inflation and trend don't dominate)
WITH m AS (
    SELECT commodity,
           SUBSTR(price_date, 1, 4) AS yr,
           CAST(SUBSTR(price_date, 6, 2) AS INTEGER) AS month_no,
           AVG(modal_price) AS month_avg
    FROM fact_prices WHERE is_outlier = 0
    GROUP BY commodity, yr, month_no
), y AS (
    SELECT commodity, yr, AVG(month_avg) AS year_avg FROM m GROUP BY commodity, yr
)
SELECT m.commodity, m.month_no,
       ROUND(AVG(m.month_avg / y.year_avg), 3) AS seasonal_index,
       RANK() OVER (PARTITION BY m.commodity ORDER BY AVG(m.month_avg / y.year_avg) DESC) AS best_sell_rank
FROM m JOIN y ON y.commodity = m.commodity AND y.yr = m.yr
GROUP BY m.commodity, m.month_no
ORDER BY m.commodity, best_sell_rank;

-- name: moving_average_and_volatility
-- Q: 7-day / 30-day moving averages and rolling volatility per commodity
SELECT commodity, price_date, ROUND(avg_modal_price, 0) AS price,
       ROUND(AVG(avg_modal_price) OVER w7, 0)  AS ma_7d,
       ROUND(AVG(avg_modal_price) OVER w30, 0) AS ma_30d,
       ROUND(100.0 * (MAX(avg_modal_price) OVER w30 - MIN(avg_modal_price) OVER w30)
             / AVG(avg_modal_price) OVER w30, 1) AS range_pct_30d
FROM v_daily_commodity
WINDOW w7  AS (PARTITION BY commodity ORDER BY price_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
       w30 AS (PARTITION BY commodity ORDER BY price_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
ORDER BY commodity, price_date;

-- name: market_price_gap_last_30d
-- Q: Which markets pay above / below the state average right now? (where to sell)
WITH recent AS (
    SELECT commodity, market, AVG(modal_price) AS mkt_avg, COUNT(*) AS n_obs
    FROM fact_prices
    WHERE is_outlier = 0
      AND price_date >= DATE((SELECT MAX(price_date) FROM fact_prices), '-30 day')
    GROUP BY commodity, market
    HAVING n_obs >= 5
), state_avg AS (
    SELECT commodity, AVG(mkt_avg) AS state_avg FROM recent GROUP BY commodity
)
SELECT r.commodity, r.market, ROUND(r.mkt_avg, 0) AS avg_price,
       ROUND(s.state_avg, 0) AS state_avg,
       ROUND(100.0 * (r.mkt_avg - s.state_avg) / s.state_avg, 1) AS premium_pct,
       RANK() OVER (PARTITION BY r.commodity ORDER BY r.mkt_avg DESC) AS price_rank
FROM recent r JOIN state_avg s USING (commodity)
ORDER BY r.commodity, price_rank;

-- name: sudden_price_drops
-- Q: Where did price fall >15% below its 30-day average in the latest week? (early-warning list)
WITH d AS (
    SELECT commodity, price_date, avg_modal_price,
           AVG(avg_modal_price) OVER (PARTITION BY commodity ORDER BY price_date
                                      ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS prev_30d_avg
    FROM v_daily_commodity
)
SELECT commodity, price_date, ROUND(avg_modal_price, 0) AS price, ROUND(prev_30d_avg, 0) AS prev_30d_avg,
       ROUND(100.0 * (avg_modal_price - prev_30d_avg) / prev_30d_avg, 1) AS change_pct
FROM d
WHERE prev_30d_avg IS NOT NULL
  AND avg_modal_price < 0.85 * prev_30d_avg
  AND price_date >= DATE((SELECT MAX(price_date) FROM fact_prices), '-7 day')
ORDER BY change_pct;
