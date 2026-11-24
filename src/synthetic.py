"""TEST-ONLY synthetic data generator.

Purpose: lets you run and debug the whole pipeline before you have real data.
The output is tagged with the file prefix 'synthetic_' and must NEVER be used for
the insights, screenshots or numbers you show recruiters. Delete data/raw/synthetic_*
before running the real analysis.

It deliberately injects real-world mess (bad dates, text prices, swapped min/max,
duplicates, outliers) so the cleaning code has something to do.
"""
import numpy as np
import pandas as pd
from config import RAW_DIR

rng = np.random.default_rng(42)

CROPS = {  # base Rs/quintal, seasonal amplitude, peak month
    "Onion": (1800, 0.35, 10), "Tomato": (2200, 0.45, 7), "Soyabean": (4500, 0.12, 6),
    "Cotton": (6800, 0.08, 3), "Tur(Arhar Fali)": (7200, 0.10, 4), "Orange": (4000, 0.25, 12),
}
MARKETS = [("Nashik", "Lasalgaon"), ("Pune", "Pune"), ("Nagpur", "Nagpur"), ("Akola", "Akola"),
           ("Latur", "Latur"), ("Solapur", "Solapur"), ("Amravati", "Amravati"), ("Kolhapur", "Kolhapur")]


def main(start="2023-01-01", end="2025-12-31"):
    dates = pd.date_range(start, end, freq="D")
    rows = []
    for crop, (base, amp, peak) in CROPS.items():
        for district, market in MARKETS:
            m_off = rng.normal(0, 0.06)               # each market has a price level offset
            walk = np.cumsum(rng.normal(0, 0.004, len(dates)))
            season = amp * np.cos(2 * np.pi * (dates.month - peak) / 12)
            price = base * np.exp(m_off + season + walk)
            keep = rng.random(len(dates)) > 0.25       # markets don't report every day
            for d, p in zip(dates[keep], price[keep]):
                lo, hi = p * rng.uniform(0.9, 0.97), p * rng.uniform(1.03, 1.12)
                rows.append(["Maharashtra", district, market, crop, "Other", "FAQ",
                             d.strftime("%d/%m/%Y"), round(lo), round(hi), round(p)])
    df = pd.DataFrame(rows, columns=["state", "district", "market", "commodity", "variety",
                                     "grade", "arrival_date", "min_price", "max_price", "modal_price"])
    df = df.astype({"min_price": object, "max_price": object, "modal_price": object})
    n = len(df)
    # inject mess
    idx = rng.choice(n, int(n * 0.004), replace=False); df.loc[idx, "modal_price"] = "NA"
    idx = rng.choice(n, int(n * 0.003), replace=False); df.loc[idx, "min_price"] = "-"
    idx = rng.choice(n, int(n * 0.005), replace=False)
    df.loc[idx, ["min_price", "max_price"]] = df.loc[idx, ["max_price", "min_price"]].values
    idx = rng.choice(n, int(n * 0.002), replace=False); df.loc[idx, "arrival_date"] = "31/02/2024"
    idx = rng.choice(n, int(n * 0.002), replace=False)
    df.loc[idx, "modal_price"] = df.loc[idx, "modal_price"].apply(lambda v: v if isinstance(v, str) else v * 10)
    # genuine price spikes (all three prices x4) - should be caught by the outlier flag
    idx = rng.choice(n, int(n * 0.002), replace=False)
    for c in ["min_price", "max_price", "modal_price"]:
        df.loc[idx, c] = df.loc[idx, c].apply(lambda v: v if isinstance(v, str) else v * 4)
    idx = rng.choice(n, int(n * 0.004), replace=False)
    df.loc[idx, "market"] = df.loc[idx, "market"].str.upper() + " "
    df = pd.concat([df, df.sample(int(n * 0.01), random_state=1)], ignore_index=True)  # duplicates
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / "synthetic_maharashtra_TEST_ONLY.csv"
    df.to_csv(out, index=False)
    print(f"wrote {len(df):,} synthetic rows -> {out}")


if __name__ == "__main__":
    main()
