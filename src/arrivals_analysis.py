"""Arrivals vs price, onion type (Lal vs Unhali) and price-spike analysis on the NHRDF Maharashtra data.

Outputs: data/processed/arrivals_*.csv and docs/arrivals_insights.md
Usage:   python src/arrivals_analysis.py     (run after ingest.py)

Method note: price and arrivals both move with the seasons, so the regression compares a market with ITSELF
(market fixed effects) after removing month-of-year effects. The result is an association, not proof of cause.
"""
import sqlite3
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import DB_PATH, PROC_DIR, DOCS_DIR


def main():
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    d = pd.read_sql("SELECT * FROM fact_prices WHERE is_outlier = 0", con, parse_dates=["price_date"])
    con.close()
    d = d[(d.arrivals_qtl > 0) & (d.modal_price > 0)]

    # ---- market-week panel
    d["week"] = d.price_date.dt.to_period("W-SUN").dt.start_time
    mk = d.groupby(["market", "week"]).agg(price=("modal_price", "mean"), arrivals=("arrivals_qtl", "sum"),
                                           days=("price_date", "nunique")).reset_index()
    counts = mk.groupby("market").size()
    keep = counts[counts >= 40].index
    mk = mk[mk.market.isin(keep)].copy()
    # a week with 1 reporting day would otherwise look like "low supply" next to a week with 5 days
    mk["arrivals_per_day"] = mk.arrivals / mk.days
    mk["lp"], mk["la"] = np.log(mk.price), np.log(mk.arrivals_per_day)
    mk["month"] = mk.week.dt.month
    fit = smf.ols("lp ~ la + C(market) + C(month)", data=mk).fit(cov_type="cluster", cov_kwds={"groups": mk["market"].astype("category").cat.codes})
    b, lo, hi, pv = fit.params["la"], *fit.conf_int().loc["la"], fit.pvalues["la"]
    pd.DataFrame([{"markets_used": mk.market.nunique(), "market_weeks": len(mk), "elasticity": b, "ci_low": lo,
                   "ci_high": hi, "p_value": pv, "r_squared": fit.rsquared}]).to_csv(PROC_DIR / "arrivals_elasticity.csv", index=False)
    mk.to_csv(PROC_DIR / "arrivals_market_weekly.csv", index=False)

    # ---- Lal vs Unhali at the same market and week
    v = d[d.variety.notna()].groupby(["market", "week", "variety"])["modal_price"].mean().unstack("variety").dropna()
    var_txt = ""
    if {"Lal (red)", "Unhali (summer)"} <= set(v.columns) and len(v):
        v["unhali_premium_pct"] = (v["Unhali (summer)"] / v["Lal (red)"] - 1) * 100
        v.reset_index().to_csv(PROC_DIR / "arrivals_variety_gap.csv", index=False)
        by_m = v.reset_index().assign(month=lambda x: x.week.dt.month).groupby("month")["unhali_premium_pct"].median()
        var_txt = (f"- Summer (Unhali) vs red (Lal) onion at the same market and week: median premium "
                   f"{v['unhali_premium_pct'].median():.0f}% over {len(v)} market-weeks; premium ranges from "
                   f"{by_m.min():.0f}% (month {int(by_m.idxmin())}) to {by_m.max():.0f}% (month {int(by_m.idxmax())}).")

    # ---- spikes and crashes in the weekly state price
    w = d.groupby("week")["modal_price"].median()
    chg4 = (w / w.shift(4) - 1) * 100
    spikes = pd.concat([chg4.sort_values(ascending=False).head(5).rename("change_4w_pct").to_frame().assign(kind="spike"),
                        chg4.sort_values().head(5).rename("change_4w_pct").to_frame().assign(kind="crash")])
    spikes["price"] = w.loc[spikes.index]
    spikes.to_csv(PROC_DIR / "arrivals_spikes.csv")
    up, dn = spikes[spikes.kind == "spike"].iloc[0], spikes[spikes.kind == "crash"].iloc[0]
    up_d, dn_d = spikes[spikes.kind == "spike"].index[0], spikes[spikes.kind == "crash"].index[0]

    lines = ["# Arrivals, onion type and price swings: auto-generated findings", "",
             "**Verify each number against the CSVs before publishing. Data window: "
             f"{d.price_date.min():%b %Y} to {d.price_date.max():%b %Y}.**", "",
             f"- Within the same market, a 10% higher average daily arrival goes with about **{b * 10:.1f}%** change in price "
             f"(95% interval {lo * 10:.1f}% to {hi * 10:.1f}%; {mk.market.nunique()} markets, {len(mk):,} market-weeks, p={pv:.3f}). Association, not proof of cause.",
             var_txt,
             f"- Largest 4-week price rise (state median): **{up_d:%d %b %Y}**, +{up.change_4w_pct:.0f}% to Rs {up.price:,.0f}/quintal.",
             f"- Largest 4-week price fall: **{dn_d:%d %b %Y}**, {dn.change_4w_pct:.0f}% to Rs {dn.price:,.0f}/quintal."]
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "arrivals_insights.md").write_text("\n".join(l for l in lines if l is not None) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
