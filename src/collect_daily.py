"""Pull today's mandi prices from the data.gov.in API and save as a dated raw CSV.

The API serves the CURRENT day's prices, not history. Run this every day
(see .github/workflows/daily_collect.yml) and your own historical dataset
builds up over time. That self-built dataset is a portfolio asset in itself.

Usage:  python src/collect_daily.py
"""
import os
import sys
import time
from datetime import date

import pandas as pd
import requests
from dotenv import load_dotenv

from config import API_URL, RAW_DIR, STATE

PAGE = 1000


def fetch_all(api_key: str, state: str) -> pd.DataFrame:
    rows, offset = [], 0
    while True:
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": PAGE,
            "offset": offset,
            "filters[state]": state,
        }
        for attempt in range(4):
            try:
                r = requests.get(API_URL, params=params, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException as exc:
                wait = 2 ** attempt
                if isinstance(exc, requests.ConnectionError) and attempt == 0:
                    print("Connection failed. The API host may have changed; see the note in config.py "
                          "(DATA_GOV_API_BASE).", file=sys.stderr)
                print(f"request failed ({exc}); retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
        else:
            raise SystemExit("API unreachable after retries")
        batch = r.json().get("records", [])
        rows.extend(batch)
        print(f"fetched {len(batch)} records (offset {offset})")
        if len(batch) < PAGE:
            break
        offset += PAGE
    return pd.DataFrame(rows)


def main():
    load_dotenv()
    key = os.getenv("DATA_GOV_API_KEY")
    if not key:
        raise SystemExit("Set DATA_GOV_API_KEY in .env (see .env.example)")
    df = fetch_all(key, STATE)
    if df.empty:
        raise SystemExit("No records returned - check the key, state filter and resource ID.")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"api_{STATE.lower()}_{date.today().isoformat()}.csv"
    df.to_csv(out, index=False)
    print(f"saved {len(df)} rows -> {out}")


if __name__ == "__main__":
    main()
