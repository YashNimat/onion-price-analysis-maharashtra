# Power BI build guide

Power BI files (.pbix) can't be generated from code, so this is a precise build spec.
Allow ~3-4 hours. Publish screenshots + a short screen recording; many recruiters won't install Power BI Desktop.

## 1. Load data (Get Data -> Text/CSV, from `data/processed/`)
| Table | File | Role |
|---|---|---|
| fact_prices | fact_prices_clean.csv | daily facts (detail) |
| weekly_prices | weekly_prices.csv | weekly state-level history |
| forecast | forecast.csv | forecast + 80% interval |
| seasonal_index | seasonal_index.csv | month x commodity index |
| market_spread | market_spread.csv | last-30-day market premium |
| recommendations | recommendations.csv | sell / hold output |
| model_backtest | model_backtest.csv | model accuracy |
| dim_date | dim_date.csv | calendar (mark as date table on `date`) |
| arrivals_weekly | arrivals_market_weekly.csv | market-week price and average daily arrivals |
| variety_gap | arrivals_variety_gap.csv | Lal vs Unhali price gap by market-week |
| spikes | arrivals_spikes.csv | biggest 4-week rises and falls |
| dim_commodity | Enter Data / `DISTINCT` of commodity | shared slicer table |

Power Query: set types, `price_date`/`week_start`/`best_week` as Date, remove nothing else (cleaning is already done in Python/SQL; say so in the README).

## 2. Model
- `dim_commodity[commodity]` 1-to-many -> every table's `commodity` (single direction).
- `dim_date[date]` 1-to-many -> `fact_prices[price_date]`, `weekly_prices[week_start]`, `forecast[week_start]`, `recommendations[best_week]`.
- Hide key columns from report view. Create a Measures table to hold the measures below.

## 3. DAX measures
```DAX
Latest Week = MAX ( weekly_prices[week_start] )

Current Price =
CALCULATE ( AVERAGE ( weekly_prices[price] ),
            weekly_prices[week_start] = [Latest Week] )

4W Avg Price =
CALCULATE ( AVERAGE ( weekly_prices[price] ),
            DATESINPERIOD ( dim_date[date], [Latest Week], -28, DAY ) )

Price LY =
CALCULATE ( AVERAGE ( weekly_prices[price] ), SAMEPERIODLASTYEAR ( dim_date[date] ) )

YoY % = DIVIDE ( AVERAGE ( weekly_prices[price] ) - [Price LY], [Price LY] )

Volatility (CV) =
DIVIDE ( STDEV.P ( weekly_prices[price] ), AVERAGE ( weekly_prices[price] ) )

Forecast Price = AVERAGE ( forecast[forecast] )
Forecast Low   = AVERAGE ( forecast[lower_80] )
Forecast High  = AVERAGE ( forecast[upper_80] )

Peak Forecast Price = MAX ( forecast[forecast] )

Expected Uplift % = DIVIDE ( [Peak Forecast Price] - [Current Price], [Current Price] )

Recommended Action = SELECTEDVALUE ( recommendations[action], "Select one commodity" )

Forecast Confidence = SELECTEDVALUE ( recommendations[confidence], "-" )

Model MAPE % = AVERAGE ( model_backtest[mape_pct] )

Market Premium % = AVERAGE ( market_spread[premium_pct] ) / 100

Best Month =
VAR top = TOPN ( 1, VALUES ( seasonal_index[month_no] ), CALCULATE ( AVERAGE ( seasonal_index[seasonal_index] ) ), DESC )
RETURN FORMAT ( DATE ( 2000, MAXX ( top, seasonal_index[month_no] ), 1 ), "MMMM" )
```

## 4. Pages
**Page 1 - Decision summary** (what a recruiter sees first)
- Slicer: commodity (single select). Cards: Current Price, Expected Uplift %, Recommended Action, Forecast Confidence.
- Table: recommendations (all commodities) with conditional-format icons on `action`.
- Title is a question: "When should a Maharashtra farmer sell?"

**Page 2 - Price trend & forecast**
- Line chart: weekly price (actual) + forecast with lower/upper as an error band. Slicers: year, commodity.
- Small multiples or a second line: this year vs last year.

**Page 3 - Seasonality**
- Matrix: rows = commodity, columns = month; value = seasonal_index; conditional formatting (diverging colour centred on 1.00).
- Column chart: seasonal index for the selected commodity.

**Page 4 - Where to sell**
- Bar chart: market premium % vs state average (last 30 days), sorted.
- Scatter or table: market, average price, number of observations (so readers see how much to trust each bar).

**Page 4b - Arrivals and price swings** (strongest page for this dataset)
- Scatter: log arrivals per day vs log price by market (add a trend line); card with the elasticity from `arrivals_elasticity.csv`.
- Column chart: Unhali vs Lal premium by month. Table: biggest spikes and crashes (`arrivals_spikes.csv`).
- Add a text box with the 2020 price swing story (use only facts you can source, such as the Sept 2020 export ban).

**Page 5 - Method & data quality**
- Table: model_backtest (MAPE per model; highlight the naive baseline).
- Text box: cleaning log summary (copy from docs/data_cleaning_log.md), data window, limitations.

## 5. Polish checklist
- One colour theme (`powerbi/theme.json`: View -> Themes -> Browse for themes).
- Every chart has a title that states the insight, not the field name.
- Axis units labelled (Rs per quintal). Tooltips on. Alt text on visuals.
- Tab order set; no default blue "Sum of ..." titles; consistent number formats.
- Export PDF + 5 screenshots into `docs/screenshots/`. Optionally Publish to web (check data licence first).
