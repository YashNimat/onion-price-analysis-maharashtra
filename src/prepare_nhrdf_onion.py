"""Convert the NHRDF onion CSVs (from github.com/amitkaps/onions-dataset, MIT licence) into the
project's raw format, keeping Maharashtra markets only.

Input : data/source_nhrdf/onions-*.csv   (Date, Market, Arrival(q), Price Minimum/Maximum/Modal (Rs/q))
Output: data/raw/nhrdf_onion_maharashtra.csv

Source data: NHRDF (National Horticultural Research & Development Foundation) market arrivals and prices.
"""
import glob
import pandas as pd
from config import ROOT, RAW_DIR

files = sorted(glob.glob(str(ROOT / "data" / "source_nhrdf" / "onions-*.csv")))
if not files:
    raise SystemExit("No files found in data/source_nhrdf/. Copy onions-2020.csv etc. there.")

df = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
print(f"loaded {len(df):,} rows from {len(files)} files")

# Market names come in several styles:
#   "KOLHAPUR(MS)"          -> state code in brackets
#   "Lasalgaon (LAL)"       -> LAL / UNHALI are onion TYPES (red / summer) at markets that are all in Maharashtra
#   "NAGPUR", "MUMBAI"      -> no suffix at all
# The old filter looked only for "(MS)" and silently dropped the biggest onion markets.
df = df[df["Market"].str.strip().str.lower() != "total"].copy()          # drop the source's own 'Total' rows
parts = df["Market"].str.extract(r"^\s*(?P<market>.*?)\s*\((?P<code>[^)]*)\)\s*$")
df["market"] = parts["market"].fillna(df["Market"].str.strip())
df["code"] = parts["code"].fillna("").str.strip().str.upper()

MH_TYPED = {"LASALGAON", "PIMPALGAON", "SOLAPUR", "YEOLA"}               # markets reported as LAL / UNHALI
MH_UNCODED = {"NAGPUR", "MUMBAI"}
is_ms = df["code"].eq("MS")
is_typed = df["code"].isin(["LAL", "UNHALI"]) & df["market"].str.upper().isin(MH_TYPED)
is_plain = df["code"].eq("") & df["market"].str.upper().isin(MH_UNCODED)
df = df[is_ms | is_typed | is_plain].copy()
df["variety"] = df["code"].map({"LAL": "Lal (red)", "UNHALI": "Unhali (summer)"})
print(f"kept {len(df):,} Maharashtra rows ({df['market'].str.upper().nunique()} markets): "
      f"{int(is_ms.sum()):,} coded MS, {int(is_typed.sum()):,} LAL/UNHALI, {int(is_plain.sum()):,} uncoded")

out = pd.DataFrame({
    "state": "Maharashtra",
    "district": pd.NA,                      # not in this source
    "market": df["market"],
    "commodity": "Onion",
    "variety": df["variety"],
    "grade": pd.NA,
    "arrival_date": pd.to_datetime(df["Date"], format="%d/%b/%Y", errors="coerce").dt.strftime("%Y-%m-%d"),
    "min_price": df["Price Minimum (Rs/q)"],
    "max_price": df["Price Maximum (Rs/q)"],
    "modal_price": df["Modal Price (Rs/q)"],
    "arrivals": df["Arrival(q)"],           # quintals
})
RAW_DIR.mkdir(parents=True, exist_ok=True)
path = RAW_DIR / "nhrdf_onion_maharashtra.csv"
out.to_csv(path, index=False)
print(f"saved {len(out):,} rows -> {path}")
