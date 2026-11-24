-- Star-style schema for mandi prices (SQLite).
DROP VIEW  IF EXISTS v_daily_commodity;
DROP TABLE IF EXISTS fact_prices;
DROP TABLE IF EXISTS dim_market;

CREATE TABLE fact_prices (
    price_date    TEXT NOT NULL,          -- ISO yyyy-mm-dd
    state         TEXT NOT NULL,
    district      TEXT,
    market        TEXT NOT NULL,
    commodity     TEXT NOT NULL,
    variety       TEXT,
    grade         TEXT,
    min_price     REAL,                   -- Rs per quintal
    max_price     REAL,
    modal_price   REAL NOT NULL,
    arrivals_qtl  REAL,
    is_outlier    INTEGER DEFAULT 0,
    source_file   TEXT
);
CREATE INDEX ix_fp_comm_date ON fact_prices (commodity, price_date);
CREATE INDEX ix_fp_market    ON fact_prices (market, commodity);

CREATE TABLE dim_market (
    state    TEXT,
    district TEXT,
    market   TEXT
);

-- Daily commodity price across markets, outliers excluded
CREATE VIEW v_daily_commodity AS
SELECT price_date,
       commodity,
       COUNT(DISTINCT market) AS markets_reporting,
       AVG(modal_price)       AS avg_modal_price,
       MIN(modal_price)       AS min_modal_price,
       MAX(modal_price)       AS max_modal_price
FROM fact_prices
WHERE is_outlier = 0
GROUP BY price_date, commodity;
