"""Long-run monthly analysis of Lasalgaon onion prices and arrivals (Mendeley dataset, DOI 10.17632/9dn4g8m97m.1).

Input : the downloaded .xlsx or .csv with columns like
        Month Name | Year | Arrival (q) | Modal Price (Rs/q) | Arrival ('000q) | Time
Usage : python src/lasalgaon_monthly.py "data/raw/LasalgaonOnionData.xlsx"
Output: data/processed/lasalgaon/*.csv  and  docs/lasalgaon_insights.md

Prices are NOMINAL rupees (not inflation adjusted), so seasonal indices are computed against each year's own
average, which removes the long-run inflation trend.
"""
import sys
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from config import PROC_DIR, DOCS_DIR

warnings.filterwarnings("ignore")
OUT = PROC_DIR / "lasalgaon"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load(path: str):
    df = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    low = {c: c.lower() for c in df.columns}
    month_c = next(c for c, l in low.items() if "month" in l)
    year_c = next(c for c, l in low.items() if l == "year")
    price_c = next(c for c, l in low.items() if "price" in l)
    arr_c = next(c for c, l in low.items() if "arrival" in l and "000" not in l)
    arr_k = next((c for c, l in low.items() if "arrival" in l and "000" in l), None)

    log = [("Raw rows", len(df))]
    out = pd.DataFrame({
        "month": df[month_c].astype(str).str.strip().str[:3].str.title(),
        "year": pd.to_numeric(df[year_c], errors="coerce"),
        "arrival_q": pd.to_numeric(df[arr_c], errors="coerce"),
        "modal_price": pd.to_numeric(df[price_c], errors="coerce"),
    })
    if arr_k:                                   # redundant column: use it only as a consistency check
        mism = (out["arrival_q"] / 1000 - pd.to_numeric(df[arr_k], errors="coerce")).abs() > 0.01
        log.append(("Rows where Arrival(q) and Arrival('000q) disagree", int(mism.sum())))
    out["month_no"] = out["month"].map({m: i + 1 for i, m in enumerate(MONTHS)})
    bad = out[["month_no", "year", "modal_price"]].isna().any(axis=1)
    log.append(("Rows with unreadable month/year/price dropped", int(bad.sum())))
    out = out[~bad]
    nonpos = (out["modal_price"] <= 0)
    log.append(("Rows with price <= 0 dropped", int(nonpos.sum())))
    out = out[~nonpos]
    out["date"] = pd.to_datetime(dict(year=out["year"].astype(int), month=out["month_no"].astype(int), day=1))
    dups = out.duplicated("date").sum()
    log.append(("Duplicate months dropped", int(dups)))
    out = out.drop_duplicates("date").sort_values("date").set_index("date")
    full = pd.date_range(out.index.min(), out.index.max(), freq="MS")
    log.append(("Missing months inside the range (interpolated if <= 6 in a row)", int(len(full) - len(out) + 0)))
    out = out.reindex(full)
    out["is_interpolated"] = out["modal_price"].isna()
    out["modal_price"] = out["modal_price"].interpolate(limit=6, limit_area="inside")   # gaps up to 6 months
    out["arrival_q"] = out["arrival_q"].interpolate(limit=6, limit_area="inside")
    out["year"], out["month_no"] = out.index.year, out.index.month
    log.append(("Final months", int(out["modal_price"].notna().sum())))
    still_missing = int(out["modal_price"].isna().sum())
    if still_missing:
        raise SystemExit(f"{still_missing} month(s) are still missing after interpolation (gaps longer than 6 months). "
                         "Monthly models need an unbroken series; fix or trim the data first.")
    return out, log


def mape(a, p):
    a, p = np.asarray(a), np.asarray(p)
    return float(np.mean(np.abs((a - p) / a)) * 100)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python src/lasalgaon_monthly.py "path/to/file.xlsx"')
    OUT.mkdir(parents=True, exist_ok=True)
    df, log = load(sys.argv[1])
    y = df["modal_price"]
    print(f"{len(y)} months: {y.index.min():%b %Y} -> {y.index.max():%b %Y}")
    for r, c in log:
        print(f"  {r}: {c:,}")

    # ---- YoY, volatility by year
    df["yoy_pct"] = y.pct_change(12) * 100
    yearly = df.groupby("year").agg(avg_price=("modal_price", "mean"), cv_pct=("modal_price", lambda s: s.std() / s.mean() * 100),
                                    min_price=("modal_price", "min"), max_price=("modal_price", "max"),
                                    total_arrival_q=("arrival_q", "sum"), months=("modal_price", "count")).reset_index()
    yearly["peak_to_trough_x"] = yearly["max_price"] / yearly["min_price"]
    yearly.to_csv(OUT / "yearly_summary.csv", index=False)

    # ---- seasonal index (complete years only)
    full_years = df.groupby("year")["month_no"].nunique()
    full_years = full_years[full_years == 12].index
    d = df[df.year.isin(full_years)].copy()
    d["idx"] = d["modal_price"] / d.groupby("year")["modal_price"].transform("mean")
    si = d.groupby("month_no")["idx"].agg(seasonal_index="mean", std="std").reset_index()
    si["month"] = si["month_no"].map(lambda m: MONTHS[m - 1])
    si["best_sell_rank"] = si["seasonal_index"].rank(ascending=False).astype(int)
    si["years_used"] = len(full_years)
    si.to_csv(OUT / "seasonal_index.csv", index=False)

    # ---- arrivals vs price: within-year deviations remove inflation and trend
    d["lp"] = np.log(d["modal_price"] / d.groupby("year")["modal_price"].transform("mean"))
    d["la"] = np.log(d["arrival_q"] / d.groupby("year")["arrival_q"].transform("mean"))
    dd = d.dropna(subset=["lp", "la"])
    fit = sm.OLS(dd["lp"], sm.add_constant(dd["la"])).fit()
    elasticity, r2, pval = float(fit.params["la"]), float(fit.rsquared), float(fit.pvalues["la"])

    # ---- biggest month-on-month spikes (the "onion crises")
    mom = y.pct_change() * 100
    spikes = mom.sort_values(ascending=False).head(10).rename("mom_change_pct").to_frame()
    spikes["price"] = y.loc[spikes.index]
    spikes.to_csv(OUT / "biggest_spikes.csv")

    # ---- forecast with backtest (last 24 months held out)
    H = 24
    train, test = y.iloc[:-H], y.iloc[-H:]
    res = {}
    res["Naive (last value)"] = mape(test, np.repeat(train.iloc[-1], H))
    res["Seasonal naive (same month last year)"] = mape(test, np.tile(train.iloc[-12:].values, 2)[:H])
    hw = ExponentialSmoothing(np.log(train.values), trend="add", damped_trend=True, seasonal="add",
                              seasonal_periods=12, initialization_method="estimated").fit()
    res["Holt-Winters (damped, seasonal)"] = mape(test, np.exp(hw.forecast(H)))
    bt = pd.DataFrame({"model": list(res), "mape_pct": list(res.values()), "train_months": len(train), "holdout_months": H})
    bt.to_csv(OUT / "model_backtest.csv", index=False)

    best = min(res, key=res.get)
    full_fit = ExponentialSmoothing(np.log(y.values), trend="add", damped_trend=True, seasonal="add",
                                    seasonal_periods=12, initialization_method="estimated").fit()
    fdates = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(), periods=12, freq="MS")
    sd = float(np.std(full_fit.resid))
    fc = np.exp(full_fit.forecast(12))
    pd.DataFrame({"date": fdates, "forecast": fc, "lower_80": fc * np.exp(-1.2816 * sd), "upper_80": fc * np.exp(1.2816 * sd),
                  "model": "Holt-Winters (damped, seasonal)"}).to_csv(OUT / "forecast_12m.csv", index=False)

    df.reset_index(names="date").to_csv(OUT / "monthly_clean.csv", index=False)

    # ---- auto-written insights (paste into README after you read and verify them)
    top, low = si.sort_values("seasonal_index").iloc[-1], si.sort_values("seasonal_index").iloc[0]
    worst_year = yearly.sort_values("cv_pct").iloc[-1]
    lines = [
        "# Lasalgaon onion: auto-generated findings",
        "",
        f"Data: {y.index.min():%b %Y} to {y.index.max():%b %Y} ({len(y)} months), nominal Rs per quintal. **Verify every number before publishing.**",
        "",
        f"- Seasonality: prices are highest in **{top['month']}** (index {top['seasonal_index']:.2f}) and lowest in **{low['month']}** (index {low['seasonal_index']:.2f}), based on {len(full_years)} complete years.",
        f"- Most volatile year: **{int(worst_year['year'])}** (coefficient of variation {worst_year['cv_pct']:.0f}%, peak-to-trough {worst_year['peak_to_trough_x']:.1f}x).",
        f"- Arrivals vs price: a 10% higher-than-usual monthly arrival goes with about **{elasticity * 10:.1f}%** change in price (R-squared {r2:.2f}, p-value {pval:.3f}). Association, not proof of cause.",
        f"- Forecast test: on the last {H} months, MAPE was " + ", ".join(f"{k} {v:.1f}%" for k, v in res.items()) + f". Best: **{best}**.",
        f"- Biggest one-month jump: {spikes.index[0]:%b %Y} (+{spikes['mom_change_pct'].iloc[0]:.0f}%).",
    ]
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "lasalgaon_insights.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines[2:]))
    print(f"\nSaved CSVs to {OUT}")


if __name__ == "__main__":
    main()
