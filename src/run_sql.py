"""Run every named query in sql/02_analysis.sql and save results to data/processed/sql_*.csv
Usage: python src/run_sql.py            (prints the first rows of each result)
"""
import re
import sqlite3
import pandas as pd
from config import DB_PATH, PROC_DIR, ROOT


def main():
    text = (ROOT / "sql" / "02_analysis.sql").read_text()
    blocks = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)[1:]
    con = sqlite3.connect(DB_PATH)
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    for name, body in zip(blocks[::2], blocks[1::2]):
        df = pd.read_sql(body.strip().rstrip(";"), con)
        df.to_csv(PROC_DIR / f"sql_{name}.csv", index=False)
        print(f"\n== {name}  ({len(df):,} rows)")
        print(df.head(6).to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
