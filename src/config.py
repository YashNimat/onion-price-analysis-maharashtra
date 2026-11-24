"""Central configuration. Edit here, not inside the scripts."""
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
DB_PATH = ROOT / "db" / "mandi.db"
DOCS_DIR = ROOT / "docs"

# data.gov.in resource: "Current Daily Price of Various Commodities from Various Markets (Mandi)"
# Verify this ID on data.gov.in before relying on it - catalogue IDs can change.
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
import os
# One source reports the old host (api.data.gov.in) stopped accepting connections on 30 Sep 2026.
# If collect_daily.py cannot connect, set DATA_GOV_API_BASE in .env to the address the
# data.gov.in website itself now uses (open the dataset's "API" tab / browser dev tools to find it).
API_BASE = os.getenv("DATA_GOV_API_BASE", "https://api.data.gov.in/resource")
API_URL = f"{API_BASE}/{RESOURCE_ID}"

STATE = "Maharashtra"
# Commodities to focus the analysis on (names must match the source spelling)
COMMODITIES = ["Onion"]   # add more (e.g. "Tomato", "Soyabean") when your data includes them

# Forecasting
FORECAST_WEEKS = 12
BACKTEST_WEEKS = 12
MIN_WEEKS_FOR_SEASONAL_MODEL = 104   # need ~2 years of weekly history for Holt-Winters

# Only recommend holding stock if the forecast peak beats today's price by at least this much
HOLD_THRESHOLD_PCT = 3.0

# Market comparison: use a longer window because many markets report irregularly
MARKET_WINDOW_DAYS = 180
MARKET_MIN_OBS = 10

# Forecast reliability rules
MIN_WEEKS_FOR_HIGH_CONFIDENCE = 156      # about 3 yearly cycles
MAX_PLAUSIBLE_UPLIFT_PCT = 60            # bigger forecast jumps are flagged as unreliable

# Hold-versus-sell test (src/hold_vs_sell.py). Spoilage and storage come from ICAR sources (see README).
SPOILAGE_PER_WEEK = 0.031          # ventilated storage: 42% loss over 120 days, converted to weekly
STORAGE_COST_PER_QTL_WEEK = 8.0    # Rs: ~Rs 140/quintal per season / ~17 weeks
HOLD_HORIZON_WEEKS = 12
