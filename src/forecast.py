"""Seasonality, forecasting, backtesting and sell-window recommendations.

Outputs (data/processed/, all CSV so Power BI can load them directly):
  weekly_prices.csv      weekly state-level price per commodity (history)
  seasonal_index.csv     month-of-year seasonal index + best-selling-month rank
  forecast.csv           history + forecast with 80% interval, per commodity
  model_backtest.csv     MAPE of each model on a hold-out, vs naive baselines
  recommendations.csv    one row per commodity: best week to sell, expected uplift, confidence
  market_spread.csv      last-30-day price premium by market (where to sell)
  fact_prices_clean.csv  cleaned daily facts
  dim_date.csv           calendar table for the Power BI model
"""
import warnings
import sqlite3
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from config import (DB_PATH, PROC_DIR, COMMODITIES, FORECAST_WEEKS,
                    BACKTEST_WEEKS, MIN_WEEKS_FOR_SEASONAL_MODEL, HOLD_THRESHOLD_PCT,
                    MARKET_WINDOW_DAYS, MARKET_MIN_OBS, MIN_WEEKS_FOR_HIGH_CONFIDENCE, MAX_PLAUSIBLE_UPLIFT_PCT)

warnings.filterwarnings("ignore")


def load_facts() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM fact_prices", con, parse_dates=["price_date"])
    con.close()
    return df


def weekly_series(df: pd.DataFrame, commodity: str) -> pd.Series:
    d = df[(df.commodity == commodity) & (df.is_outlier == 0)]
    # median across markets per day is robust to one market reporting oddly
    daily = d.groupby("price_date")["modal_price"].median()
    wk = daily.groupby(daily.index.to_period("W-SUN")).mean()
    wk.index = wk.index.to_timestamp()                  # Monday of each week
    full = pd.date_range(wk.index.min(), wk.index.max(), freq="W-MON")
    return wk.reindex(full).interpolate(limit=3).dropna()


def mape(actual, pred):
    actual, pred = np.asarray(actual), np.asarray(pred)
    return float(np.mean(np.abs((actual - pred) / actual)) * 100)


def hw_forecast(train: pd.Series, steps: int):
    """Holt-Winters on log prices (keeps forecasts positive, makes seasonality proportional)."""
    m = ExponentialSmoothing(np.log(train.values), trend="add", damped_trend=True,
                             seasonal="add", seasonal_periods=52,
                             initialization_method="estimated").fit()
    fc = np.exp(m.forecast(steps))
    resid_sd = float(np.std(m.resid))
    return fc, resid_sd


def forecast_models(train: pd.Series, steps: int) -> dict:
    """Return {model_name: (forecast_array, resid_sd)} for every model the data length allows."""
    out = {}
    out["Naive (last value)"] = (np.repeat(train.iloc[-1], steps),
                                 float(np.log(train).diff().std() * np.sqrt(np.arange(1, steps + 1)).mean()))
    if len(train) >= 52 + steps:
        base = train.iloc[-52:].values
        reps = int(np.ceil(steps / 52))
        sn = np.tile(base, reps)[:steps]
        out["Seasonal naive (same week last year)"] = (sn, float(np.log(train).diff(52).std()))
    if len(train) >= MIN_WEEKS_FOR_SEASONAL_MODEL:
        try:
            out["Holt-Winters (damped trend, seasonal)"] = hw_forecast(train, steps)
        except Exception as exc:             # noqa: BLE001 - fall back gracefully
            print(f"  Holt-Winters failed: {exc}")
    return out


def main():
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    facts = load_facts()
    facts_out = facts.copy()
    facts_out["price_date"] = facts_out["price_date"].dt.date
    facts_out.to_csv(PROC_DIR / "fact_prices_clean.csv", index=False)

    present = [c for c in COMMODITIES if c in set(facts.commodity)]
    missing = sorted(set(COMMODITIES) - set(present))
    if missing:
        print(f"Skipping commodities not found in data: {missing}")
    if not present:
        raise SystemExit("None of config.COMMODITIES appear in the data. Check spelling in the source.")

    weekly_rows, season_rows, fc_rows, bt_rows, rec_rows = [], [], [], [], []

    for crop in present:
        y = weekly_series(facts, crop)
        print(f"{crop}: {len(y)} weekly points ({y.index.min().date()} -> {y.index.max().date()})")
        if len(y) < BACKTEST_WEEKS + 20:
            print("  too little history; skipping forecast (keep collecting data)")
            continue

        # history
        for d, v in y.items():
            weekly_rows.append((crop, d, v))

        # seasonal index: month average / that year's average, averaged over years
        tmp = y.to_frame("p")
        tmp["yr"], tmp["m"] = tmp.index.year, tmp.index.month
        yr_avg = tmp.groupby("yr")["p"].transform("mean")
        tmp["idx"] = tmp["p"] / yr_avg
        full_years = tmp.groupby("yr")["m"].nunique()
        full_years = full_years[full_years == 12].index          # only complete years
        base = tmp[tmp.yr.isin(full_years)] if len(full_years) else tmp
        si = base.groupby("m")["idx"].mean()
        rank = si.rank(ascending=False).astype(int)
        for m_, v in si.items():
            season_rows.append((crop, int(m_), float(v), int(rank[m_]), len(full_years)))

        # backtest on the last BACKTEST_WEEKS
        train, test = y.iloc[:-BACKTEST_WEEKS], y.iloc[-BACKTEST_WEEKS:]
        results = {}
        for name, (fc, _) in forecast_models(train, BACKTEST_WEEKS).items():
            results[name] = mape(test.values, fc)
            bt_rows.append((crop, name, results[name], len(train), BACKTEST_WEEKS))
        if not results:
            continue
        best_name = min(results, key=results.get)
        best_mape = results[best_name]
        naive_mape = results.get("Naive (last value)", np.nan)

        # refit best model on ALL data and forecast ahead
        final = forecast_models(y, FORECAST_WEEKS)
        fc, sd = final.get(best_name, final["Naive (last value)"])
        fdates = pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=FORECAST_WEEKS, freq="W-MON")
        z = 1.2816                                                    # 80% interval
        lo, hi = fc * np.exp(-z * sd), fc * np.exp(z * sd)
        for d, f, l, h in zip(fdates, fc, lo, hi):
            fc_rows.append((crop, d, float(f), float(l), float(h), best_name))

        # recommendation
        current = float(y.iloc[-4:].mean())
        k = int(np.argmax(fc))
        uplift = (fc[k] / current - 1) * 100
        conf = "High" if best_mape < 8 else "Medium" if best_mape < 15 else "Low"
        # An accurate backtest on a short history still cannot be trusted for a full-year seasonal forecast,
        # and a huge forecast jump is more likely a model artefact than a real opportunity.
        if len(y) < MIN_WEEKS_FOR_HIGH_CONFIDENCE and conf == "High":
            conf = "Medium (short history)"
        if abs(uplift) > MAX_PLAUSIBLE_UPLIFT_PCT:
            conf = "Low (extreme forecast)"
        improvement = (naive_mape - best_mape) / naive_mape * 100 if naive_mape else np.nan
        if conf.startswith("Low"):
            action = "No reliable recommendation"
        else:
            action = f"Hold until {fdates[k].date()}" if uplift >= HOLD_THRESHOLD_PCT else "Sell now"
        rec_rows.append((crop, float(current), fdates[k], float(fc[k]), float(uplift),
                         best_name, float(best_mape), float(naive_mape), float(improvement), conf, action,
                         len(y), y.index[-1]))

    pd.DataFrame(weekly_rows, columns=["commodity", "week_start", "price"]).to_csv(
        PROC_DIR / "weekly_prices.csv", index=False)
    pd.DataFrame(season_rows, columns=["commodity", "month_no", "seasonal_index",
                                       "best_sell_rank", "years_used"]).to_csv(PROC_DIR / "seasonal_index.csv", index=False)
    pd.DataFrame(fc_rows, columns=["commodity", "week_start", "forecast", "lower_80", "upper_80",
                                   "model"]).to_csv(PROC_DIR / "forecast.csv", index=False)
    pd.DataFrame(bt_rows, columns=["commodity", "model", "mape_pct", "train_weeks",
                                   "holdout_weeks"]).to_csv(PROC_DIR / "model_backtest.csv", index=False)
    pd.DataFrame(rec_rows, columns=["commodity", "current_price", "best_week", "expected_price",
                                    "uplift_pct", "model", "backtest_mape_pct", "naive_mape_pct",
                                    "improvement_vs_naive_pct", "confidence", "action", "history_weeks", "data_end"]).to_csv(
        PROC_DIR / "recommendations.csv", index=False)

    # market spread (last 30 days)
    last = facts.price_date.max()
    r = facts[(facts.is_outlier == 0) & (facts.price_date >= last - pd.Timedelta(days=MARKET_WINDOW_DAYS))]
    g = r.groupby(["commodity", "market"])["modal_price"].agg(avg_price="mean", n_obs="count").reset_index()
    g = g[g.n_obs >= MARKET_MIN_OBS]
    g["state_avg"] = g.groupby("commodity")["avg_price"].transform("mean")
    g["premium_pct"] = (g.avg_price / g.state_avg - 1) * 100
    g.to_csv(PROC_DIR / "market_spread.csv", index=False)

    # calendar table
    first = facts.price_date.min()
    first = first - pd.Timedelta(days=first.weekday())            # start on the Monday so every week_start has a calendar row
    dates = pd.date_range(first, facts.price_date.max() + pd.Timedelta(weeks=FORECAST_WEEKS), freq="D")
    pd.DataFrame({"date": dates, "year": dates.year, "month_no": dates.month,
                  "month": dates.strftime("%b"), "quarter": "Q" + dates.quarter.astype(str),
                  "week_start": (dates - pd.to_timedelta(dates.weekday, unit="D")).date,
                  "is_kharif_season": dates.month.isin([6, 7, 8, 9, 10]),
                  "is_rabi_season": dates.month.isin([11, 12, 1, 2, 3])}).to_csv(
        PROC_DIR / "dim_date.csv", index=False)

    print("\nSaved outputs to", PROC_DIR)
    print(pd.read_csv(PROC_DIR / "recommendations.csv").round(1).to_string(index=False))


if __name__ == "__main__":
    main()
