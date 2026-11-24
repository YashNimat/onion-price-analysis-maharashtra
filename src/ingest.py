"""Load every raw CSV -> clean -> write to SQLite and the cleaning log.

Usage:
    python src/ingest.py                      # real data only
    python src/ingest.py --include-synthetic  # pipeline testing only
"""
import argparse
import sqlite3
import pandas as pd

from config import RAW_DIR, DB_PATH, DOCS_DIR, ROOT
from clean import clean_prices, write_cleaning_log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-synthetic", action="store_true",
                    help="include files named synthetic_* (TEST ONLY)")
    args = ap.parse_args()

    files = sorted(RAW_DIR.glob("*.csv"))
    if not args.include_synthetic:
        files = [f for f in files if not f.name.startswith("synthetic_")]
    if not files:
        raise SystemExit("No raw CSVs found in data/raw. Run collect_daily.py or add Agmarknet exports.")

    frames = []
    for f in files:
        part = pd.read_csv(f, dtype=str)
        part["source_file"] = f.name
        frames.append(part)
        print(f"loaded {f.name}: {len(part):,} rows")
    raw = pd.concat(frames, ignore_index=True)
    source_file = raw["source_file"]

    clean, log = clean_prices(raw.drop(columns=["source_file"]))
    clean["source_file"] = "multiple"

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript((ROOT / "sql" / "01_schema.sql").read_text())
    clean.to_sql("fact_prices", con, if_exists="append", index=False)
    con.execute("INSERT INTO dim_market SELECT DISTINCT state, district, market FROM fact_prices")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM fact_prices").fetchone()[0]
    con.close()

    note = (f"Source files: {', '.join(sorted(set(source_file)))}\n\n"
            + ("> **WARNING: synthetic test data included. Do not publish these numbers.**" if args.include_synthetic else ""))
    write_cleaning_log(log, DOCS_DIR / "data_cleaning_log.md", note)
    print(f"\n{n:,} clean rows in {DB_PATH}")
    for rule, count in log:
        print(f"  {rule}: {count:,}")


if __name__ == "__main__":
    main()
