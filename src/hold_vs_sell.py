"""Would storing onions have beaten selling immediately? Tested on the real weekly price history.

For every week t in the data we compare:
    sell now:        price[t]
    store k weeks:   price[t+k] * (1 - spoilage)^k  -  storage_cost * k     (per quintal)
Transport cost is the same either way, so it cancels out.

A seller cannot know the best k in advance, so the fair test is a FIXED holding period (HOLD_HORIZON_WEEKS).
The hindsight-best result is also reported to show the upper bound. Interest on tied-up money is ignored,
which flatters storing.

Outputs: data/processed/hold_vs_sell.csv, docs/hold_vs_sell_insights.md
Usage:   python src/hold_vs_sell.py   (run after forecast.py)
"""
import numpy as np
import pandas as pd
from config import (PROC_DIR, DOCS_DIR, SPOILAGE_PER_WEEK as S, STORAGE_COST_PER_QTL_WEEK as C, HOLD_HORIZON_WEEKS as H)


def breakeven_weekly_rise(p0: float) -> float:
    """Smallest constant weekly price rise for which storing H weeks beats selling now, at starting price p0."""
    lo, hi = 0.0, 0.5
    for _ in range(60):
        g = (lo + hi) / 2
        gain = p0 * (1 + g) ** H * (1 - S) ** H - C * H - p0
        lo, hi = (lo, g) if gain > 0 else (g, hi)
    return hi


def main():
    w = pd.read_csv(PROC_DIR / "weekly_prices.csv", parse_dates=["week_start"]).set_index("week_start")["price"]
    rows = []
    for t in range(len(w) - H):
        p0 = w.iloc[t]
        gains = [w.iloc[t + k] * (1 - S) ** k - C * k - p0 for k in range(1, H + 1)]
        rows.append({"week_start": w.index[t], "price_now": p0,
                     "gain_fixed_pct": gains[-1] / p0 * 100, "gain_best_pct": max(gains) / p0 * 100})
    d = pd.DataFrame(rows)
    d["hold_wins_fixed"] = d["gain_fixed_pct"] > 0
    d["hold_wins_best"] = d["gain_best_pct"] > 0
    d.to_csv(PROC_DIR / "hold_vs_sell.csv", index=False)

    n = len(d)
    fixed, best = d["hold_wins_fixed"].mean() * 100, d["hold_wins_best"].mean() * 100
    med = d["gain_fixed_pct"].median()
    by_year = d.groupby(d.week_start.dt.year)["hold_wins_fixed"].agg(["mean", "count"])
    be = {p: breakeven_weekly_rise(p) * 100 for p in (1000, 1146, 2000, 3000)}
    lines = ["# Hold versus sell: auto-generated findings", "",
             f"Test: for each of {n} start weeks, store {H} weeks (spoilage {S:.1%}/week, storage Rs {C:.0f}/quintal/week) vs sell immediately. Interest ignored.", "",
             f"- Storing {H} weeks beat selling immediately in **{fixed:.0f}%** of start weeks. With hindsight (best week chosen after the fact) it was **{best:.0f}%**.",
             f"- The median outcome of storing {H} weeks was **{med:+.0f}%** of the starting price.",
             "- Break-even weekly price rise by starting price level: " + ", ".join(f"Rs {p:,} -> {v:.1f}%" for p, v in be.items()) + ".",
             "- Share of start weeks where storing won, by year: " + ", ".join(f"{y}: {r['mean'] * 100:.0f}% (n={int(r['count'])})" for y, r in by_year.iterrows()) + "."]
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "hold_vs_sell_insights.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
