"""Central configuration for the ingestion layer.

Paths default to a local ./data folder so the whole project runs on a laptop.
On Azure, the same layout maps onto ADLS Gen2 containers (bronze/silver/gold).
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("MDW_DATA_DIR", PROJECT_ROOT / "data"))

BRONZE_DIR = DATA_DIR / "bronze"
STATE_DIR = DATA_DIR / "state"
WAREHOUSE_PATH = Path(os.getenv("MDW_WAREHOUSE", DATA_DIR / "warehouse.duckdb"))

# Free Alpha Vantage tier = 25 requests/day, 5/minute.
# Keep this list at 10-15 symbols: 1 request per symbol per daily run.
# US listings are priced in USD; London listings (".LON") are priced in pence (GBX).
TICKERS: list[str] = [
    "AAPL",
    "MSFT",
    "NVDA",
    "JPM",
    "LSEG.LON",
    "HSBA.LON",
    "BARC.LON",
    "VOD.LON",
]

# Bank of England daily spot rates (units of foreign currency per 1 GBP).
#   XUDLUSS = US dollar into sterling, XUDLERS = euro into sterling
BOE_SERIES: dict[str, str] = {
    "XUDLUSS": "USD",
    "XUDLERS": "EUR",
}

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
BOE_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"

# Full price history (outputsize=full) is a premium Alpha Vantage feature.
# The free tier returns the latest ~100 trading days per call ("compact").
# Set ALPHA_VANTAGE_PREMIUM=true in .env if you ever upgrade.
AV_FULL_HISTORY = os.getenv("ALPHA_VANTAGE_PREMIUM", "false").lower() == "true"

# Seconds to wait between Alpha Vantage calls to respect the 5 requests/minute limit.
AV_SLEEP_SECONDS = 13
