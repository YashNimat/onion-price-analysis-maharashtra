"""Cleaning rules for raw mandi price files (API dumps or Agmarknet CSV exports).

Every rule is counted, and the counts are written to docs/data_cleaning_log.md
so the README can show exactly what was wrong with the data and what you did.
"""
import re
import numpy as np
import pandas as pd

# Different sources name the same columns differently. Map them all to one schema.
COLUMN_ALIASES = {
    "state": ["state", "state name", "state_name"],
    "district": ["district", "district name", "district_name"],
    "market": ["market", "market name", "market_name"],
    "commodity": ["commodity", "commodity name", "commodity_name"],
    "variety": ["variety"],
    "grade": ["grade"],
    "price_date": ["arrival_date", "price date", "date", "reported date"],
    "min_price": ["min_price", "min price (rs./quintal)", "min x0020 price", "min price"],
    "max_price": ["max_price", "max price (rs./quintal)", "max x0020 price", "max price"],
    "modal_price": ["modal_price", "modal price (rs./quintal)", "modal x0020 price", "modal price"],
    "arrivals_qtl": ["arrivals", "arrivals (tonnes)", "arrival"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    lookup = {_norm(a): std for std, aliases in COLUMN_ALIASES.items() for a in aliases}
    df = df.rename(columns={c: lookup.get(_norm(c), _norm(c)) for c in df.columns})
    for needed in ["state", "district", "market", "commodity", "price_date",
                   "min_price", "max_price", "modal_price"]:
        if needed not in df.columns:
            raise ValueError(f"Missing required column after mapping: {needed}. Found: {list(df.columns)}")
    for optional in ["variety", "grade", "arrivals_qtl"]:
        if optional not in df.columns:
            df[optional] = np.nan
    return df[["state", "district", "market", "commodity", "variety", "grade",
               "price_date", "min_price", "max_price", "modal_price", "arrivals_qtl"]]


def clean_prices(df: pd.DataFrame):
    """Return (clean_df, log) where log is an ordered list of (rule, rows_affected)."""
    log = [("Raw rows loaded", len(df))]
    df = standardise_columns(df.copy())

    # 1. text normalisation (trailing spaces, case, stray characters in names)
    for c in ["state", "district", "market", "commodity", "variety", "grade"]:
        df[c] = df[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    df["commodity"] = df["commodity"].str.title()
    df["market"] = df["market"].str.title()
    df["district"] = df["district"].str.title()

    # 2. numeric coercion: "NA", "-", "1,200", "Rs 1200" -> numbers or NaN
    for c in ["min_price", "max_price", "modal_price", "arrivals_qtl"]:
        before_na = df[c].isna().sum()
        df[c] = pd.to_numeric(df[c].astype("string").str.replace(r"[^\d.\-]", "", regex=True),
                              errors="coerce")
        log.append((f"Non-numeric / blank values in {c} set to missing",
                    int(df[c].isna().sum() - before_na)))

    # 3. date parsing (Indian sources use dd/mm/yyyy)
    # ISO dates (YYYY-MM-DD, e.g. CEDA exports) must be parsed year-first; applying dayfirst
    # to them would silently swap day and month. Everything else is treated as dd/mm/yyyy.
    ds = df["price_date"].astype("string").str.strip()
    is_iso = ds.str.match(r"^\d{4}-\d{2}-\d{2}")
    parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    parsed[is_iso.fillna(False)] = pd.to_datetime(ds[is_iso.fillna(False)].str[:10],
                                                  format="%Y-%m-%d", errors="coerce")
    not_iso = ~is_iso.fillna(False)
    parsed[not_iso] = pd.to_datetime(ds[not_iso], dayfirst=True, errors="coerce", format="mixed")
    log.append(("Unparseable dates dropped", int(parsed.isna().sum())))
    df["price_date"] = parsed
    df = df.dropna(subset=["price_date"])

    # 4. drop rows with no usable price
    n = len(df)
    df = df[(df["modal_price"] > 0)]
    log.append(("Rows with missing / zero modal price dropped", n - len(df)))

    # 5. fix min/max swaps and fill gaps
    swapped = df["min_price"] > df["max_price"]
    log.append(("Rows where min_price > max_price (swapped back)", int(swapped.sum())))
    df.loc[swapped, ["min_price", "max_price"]] = df.loc[swapped, ["max_price", "min_price"]].values
    df["min_price"] = df["min_price"].fillna(df["modal_price"])
    df["max_price"] = df["max_price"].fillna(df["modal_price"])

    # 6. modal outside [min, max] -> clamp (data-entry error, keep the row)
    outside = (df["modal_price"] < df["min_price"]) | (df["modal_price"] > df["max_price"])
    log.append(("Rows where modal price outside min-max range (clamped)", int(outside.sum())))
    df["modal_price"] = df["modal_price"].clip(df["min_price"], df["max_price"])

    # 7. exact duplicates on the natural key (keep the last report of the day)
    key = ["price_date", "state", "district", "market", "commodity", "variety", "grade"]
    n = len(df)
    df = df.sort_values("price_date").drop_duplicates(subset=key, keep="last")
    log.append(("Duplicate market-day-commodity-variety rows removed", n - len(df)))

    # 8. outlier FLAG (not drop): robust z-score on log price within commodity+market
    lp = np.log(df["modal_price"])
    grp = lp.groupby([df["commodity"], df["market"]])
    med = grp.transform("median")
    mad = (lp - med).abs().groupby([df["commodity"], df["market"]]).transform("median")
    z = 0.6745 * (lp - med) / mad.replace(0, np.nan)
    df["is_outlier"] = (z.abs() > 6).fillna(False).astype(int)
    log.append(("Rows flagged as price outliers (kept, flag column added)", int(df["is_outlier"].sum())))

    df["price_date"] = df["price_date"].dt.date.astype(str)
    log.append(("Final clean rows", len(df)))
    return df.reset_index(drop=True), log


def write_cleaning_log(log, path, source_note=""):
    lines = ["# Data cleaning log", "", source_note, "",
             "| Step | Rows affected |", "|---|---:|"]
    lines += [f"| {rule} | {count:,} |" for rule, count in log]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
