"""Extend the Mendeley monthly Lasalgaon file with NHRDF data (Jan 2020 - Jul 2022).

Builds a monthly Lasalgaon series from data/source_nhrdf/ in the SAME layout as the Mendeley file, and
(optionally) joins the two into one continuous file that lasalgaon_monthly.py can analyse.

Usage:
    python src/extend_lasalgaon.py                                   # NHRDF monthly only
    python src/extend_lasalgaon.py "data/raw/LasIgaonOnionData.xlsx" # also build the combined file
Outputs (data/raw/): lasalgaon_nhrdf_monthly.csv, lasalgaon_combined_monthly.csv

CAUTION: the two sources may define "monthly modal price" differently. This script compares the months where
they overlap (if any) and prints the gap/overlap so you can judge, and writes that note into the console output.
Here NHRDF monthly price = arrival-weighted mean of daily modal prices across both onion types (Lal + Unhali).
"""
import glob
import sys
import numpy as np
import pandas as pd
from config import ROOT, RAW_DIR

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def nhrdf_monthly() -> pd.DataFrame:
    files = sorted(glob.glob(str(ROOT / "data" / "source_nhrdf" / "onions-*.csv")))
    if not files:
        raise SystemExit("No NHRDF files in data/source_nhrdf/")
    d = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
    d = d[d["Market"].str.upper().str.startswith("LASALGAON", na=False)].copy()
    d["date"] = pd.to_datetime(d["Date"], format="%d/%b/%Y", errors="coerce")
    d["arr"] = pd.to_numeric(d["Arrival(q)"].str.replace(",", ""), errors="coerce")
    d["px"] = pd.to_numeric(d["Modal Price (Rs/q)"].str.replace(",", ""), errors="coerce")
    d = d.dropna(subset=["date", "px"])
    d = d[d["px"] > 0]
    d["w"] = d["arr"].fillna(0)
    d["ym"] = d["date"].dt.to_period("M")

    def agg(g):
        w = g["w"].sum()
        price = np.average(g["px"], weights=g["w"]) if w > 0 else g["px"].mean()
        return pd.Series({"Arrival (q)": g["arr"].sum(), "Modal Price (Rs/q)": round(price),
                          "days_reported": g["date"].nunique()})
    m = d.groupby("ym").apply(agg, include_groups=False).reset_index()
    m["Year"] = m["ym"].dt.year
    m["Month Name"] = m["ym"].dt.month.map(lambda i: MONTHS[i - 1])
    m["month_start"] = m["ym"].dt.to_timestamp()
    return m


def main():
    m = nhrdf_monthly()
    out = m[["Month Name", "Year", "Arrival (q)", "Modal Price (Rs/q)", "days_reported"]]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(RAW_DIR / "lasalgaon_nhrdf_monthly.csv", index=False)
    print(f"NHRDF Lasalgaon monthly: {len(m)} months, {m.month_start.min():%b %Y} -> {m.month_start.max():%b %Y}")
    thin = m[m.days_reported < 5]
    print(f"  months with fewer than 5 reporting days (treat with care): {len(thin)}")
    print(f"  saved data/raw/lasalgaon_nhrdf_monthly.csv")

    if len(sys.argv) < 2:
        return
    path = sys.argv[1]
    old = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    old.columns = [str(c).strip() for c in old.columns]
    mc = next(c for c in old.columns if "month" in c.lower())
    pc = next(c for c in old.columns if "price" in c.lower())
    ac = next(c for c in old.columns if "arrival" in c.lower() and "000" not in c.lower())
    o = pd.DataFrame({"Month Name": old[mc].astype(str).str.strip(), "Year": pd.to_numeric(old["Year"], errors="coerce"),
                      "Arrival (q)": pd.to_numeric(old[ac], errors="coerce"),
                      "Modal Price (Rs/q)": pd.to_numeric(old[pc], errors="coerce")}).dropna(subset=["Year", "Modal Price (Rs/q)"])
    o["month_start"] = pd.to_datetime(o["Year"].astype(int).astype(str) + "-" + o["Month Name"].str[:3] + "-01", format="%Y-%b-%d", errors="coerce")
    o = o.dropna(subset=["month_start"])
    print(f"\nMendeley file: {len(o)} months, {o.month_start.min():%b %Y} -> {o.month_start.max():%b %Y}")

    both = o.merge(m, on="month_start", suffixes=("_old", "_new"))
    if len(both):
        ratio = (both["Modal Price (Rs/q)_new"] / both["Modal Price (Rs/q)_old"])
        print(f"Overlap: {len(both)} months. NHRDF/Mendeley price ratio: median {ratio.median():.2f}, "
              f"range {ratio.min():.2f}-{ratio.max():.2f}  (close to 1.00 = consistent definitions)")
    else:
        gap = (m.month_start.min().year - o.month_start.max().year) * 12 + m.month_start.min().month - o.month_start.max().month - 1
        print(f"No overlap. Gap between the two sources: {gap} month(s) (will be interpolated if <= 6).")

    comb = pd.concat([o[o.month_start < m.month_start.min()][["Month Name", "Year", "Arrival (q)", "Modal Price (Rs/q)"]],
                      m[["Month Name", "Year", "Arrival (q)", "Modal Price (Rs/q)"]]], ignore_index=True)
    comb["Year"] = comb["Year"].astype(int)
    comb.to_csv(RAW_DIR / "lasalgaon_combined_monthly.csv", index=False)
    print(f"Combined: {len(comb)} rows saved to data/raw/lasalgaon_combined_monthly.csv")


if __name__ == "__main__":
    main()
