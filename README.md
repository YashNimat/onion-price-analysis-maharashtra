# Is storing onions worth it? Maharashtra onion price analysis (2020-2022)

An end-to-end analytics project (Python, SQL, Excel, Power BI) on 7,426 mandi price records from 40 Maharashtra markets.
It asks a practical question: **after spoilage and storage costs, would a farmer or trader have done better storing onions for 12 weeks than selling immediately?**

**Short answer:** usually no. In 2020-22, storing for 12 weeks beat selling immediately in only **21%** of start weeks; the typical outcome was **-45%** of the starting price. The 12-week forecast is flagged unreliable, and the project says why.

> Screenshots of the five dashboard pages are in `docs/screenshots/`. Dashboard file: `powerbi/Mandi_Dashboard.pbix` (needs Power BI Desktop).

## Key findings
| Finding | Number | Source file |
|---|---|---|
| Price swing in 2020 | Rs 571 per quintal (11 May) to Rs 5,686 (19 Oct): about 10x | `weekly_prices.csv` |
| Break-even for storing | about 3.9% price rise per week at Rs 1,146/quintal (3.5% at Rs 3,000) | `docs/hold_vs_sell_insights.md` |
| Storing 12 weeks beat selling now | 21% of 123 start weeks (63% with perfect hindsight); median outcome -45% | `docs/hold_vs_sell_insights.md` |
| Seasonality (2020 and 2021 only) | highest in October (index 1.88), lowest in April (0.45) | `seasonal_index.csv` |
| Market premium, Jan to Jul 2022 | Mumbai +28% (50 prices), Aurangabad -31% (29 prices) vs average of 17 markets with at least 10 prices | `market_spread.csv` |
| Arrivals vs price | 10% higher daily arrivals goes with about -0.3% price (95% interval -0.6% to 0.0%, p = 0.059): weak, borderline | `docs/arrivals_insights.md` |
| Forecast accuracy | Holt-Winters 7.7% error vs 19.1% (naive) and 40.0% (seasonal naive) on a 12-week test | `model_backtest.csv` |
| Forecast verdict | predicts +232% by 17 Oct 2022: **flagged unreliable, no advice given** | `recommendations.csv` |

Events marked on the dashboard: onion export ban (14 Sep 2020, lifted 1 Jan 2021) and stock limits (23 Oct 2020). Sources: Economic Survey 2020-21 and PIB press release of 23 Oct 2020. The analysis does not claim these caused the price moves.

## Data
- **Source:** NHRDF onion market prices and arrivals via github.com/amitkaps/onions-dataset (MIT licence). 30,967 rows covering all of India, Jan 2020 to Jul 2022 (`data/source_nhrdf/`).
- **Prepared:** kept Maharashtra only (7,426 rows, 40 markets): 4,912 coded "MS", 1,798 Lal/Unhali onion at Lasalgaon, Pimpalgaon, Solapur and Yeola, and 716 for Nagpur and Mumbai. Removed the source's own "Total" rows. Flagged 2 price outliers (kept). Removed 0 duplicates. See `src/prepare_nhrdf_onion.py` and `docs/data_cleaning_log.md`.
- **Coverage caveat:** 132 weeks contain data (the forecast's 135 include 3 filled by interpolation). Reporting thins out after March 2022: a typical week before 2022 had about 64 prices, April to July 2022 about 15.

## Method
1. **Python** cleans and standardises the data, builds weekly series, tests three forecast models against baselines, and runs the hold-versus-sell test (`src/`).
2. **SQL** (SQLite) holds a fact table and runs window-function analysis: year-on-year change (`LAG`), seasonal index, rolling averages, and market gaps with `RANK` (`sql/`).
3. **Excel** what-if model (`outputs/Mandi_WhatIf.xlsx`): net revenue by selling week after spoilage and storage cost, with a Scenario mode because the forecast is unreliable.
4. **Power BI** five-page dashboard: Summary, Seasons, Arrivals, Forecast, Methods.

**Assumptions:** spoilage 3.1% per week (ICAR-DOGR: up to 42% loss in 4 months in ventilated storage, converted to weekly); storage Rs 8 per quintal per week (ICAR paper: Rs 140 per quintal per season, divided by about 17 weeks). Transport cost is the same for every selling week, so it cancels out of the decision. Interest on tied-up money is ignored, which flatters storing.

## Limitations
- The data ends in July 2022 and is thin at the end, so "latest price" is not today's price.
- Only two full years for seasonality, dominated by the 2020 spike.
- Mandi prices are not farm-gate prices.
- Arrivals results are associations, not proof of cause.
- The Lal/Unhali comparison rests on 101 market-weeks, and several months have fewer than 6.

## Reproduce it
```bash
pip install -r requirements.txt
python src/prepare_nhrdf_onion.py    # keep Maharashtra rows
python src/run_all.py                # ingest, SQL, forecast, arrivals, hold-vs-sell, Excel
```
Quote only numbers found in `docs/*_insights.md` and `data/processed/`. The Power BI build guide is in `powerbi/BUILD_GUIDE.md`.

## Project structure
```
src/        Python scripts (cleaning, SQL runner, forecast, arrivals, hold-vs-sell, Excel builder)
sql/        schema and analysis queries
data/       source and prepared data
docs/       cleaning log, auto-generated insights, screenshots
powerbi/    dashboard file, theme and build guide
outputs/    Excel what-if model
```
Not used for the final results: `src/collect_daily.py` (live data.gov.in collector; the API was returning errors, so the scheduled job is disabled) and `src/lasalgaon_monthly.py` / `extend_lasalgaon.py` (optional long-run monthly analysis).
