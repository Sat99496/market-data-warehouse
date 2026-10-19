"""Ingest daily equity prices from the Alpha Vantage TIME_SERIES_DAILY endpoint."""
from __future__ import annotations

from datetime import date
from typing import Any

import requests

from ingestion.config import ALPHA_VANTAGE_URL


class AlphaVantageError(RuntimeError):
    pass


def fetch_daily(symbol: str, api_key: str, full_history: bool = False, timeout: int = 30) -> dict[str, Any]:
    """Call the API once for one symbol. full_history=True returns 20+ years in one request."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "full" if full_history else "compact",
        "apikey": api_key,
    }
    response = requests.get(ALPHA_VANTAGE_URL, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    # Alpha Vantage returns HTTP 200 even for errors and rate limits.
    for key in ("Error Message", "Note", "Information"):
        if key in payload:
            raise AlphaVantageError(f"{symbol}: {payload[key]}")
    return payload


def parse_daily(payload: dict[str, Any], since: date | None = None) -> list[dict[str, Any]]:
    """Flatten the nested JSON into one row per trading day, keeping only days after `since`."""
    symbol = payload["Meta Data"]["2. Symbol"]
    series = payload["Time Series (Daily)"]
    rows = []
    for day, values in series.items():
        trade_date = date.fromisoformat(day)
        if since is not None and trade_date <= since:
            continue
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date.isoformat(),
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
                "volume": int(float(values["5. volume"])),
            }
        )
    return sorted(rows, key=lambda r: r["trade_date"])
