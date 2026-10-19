"""Synthetic data in the exact shape the real APIs return.

Lets the whole pipeline (and CI) run with no API key and no network.
Prices are a seeded random walk - they are NOT real market data.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from ingestion.config import BOE_SERIES

_START_PRICES = {
    "AAPL": 190.0, "MSFT": 410.0, "NVDA": 120.0, "JPM": 200.0,
    "LSEG.LON": 9500.0, "HSBA.LON": 700.0, "BARC.LON": 230.0, "VOD.LON": 72.0,
}


def _trading_days(start: date, end: date) -> list[date]:
    days, current = [], start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def sample_daily_payload(symbol: str, start: date, end: date, seed: int = 42) -> dict[str, Any]:
    rng = random.Random(f"{seed}-{symbol}")
    price = _START_PRICES.get(symbol, 100.0)
    series = {}
    for day in _trading_days(start, end):
        open_ = price
        close = max(0.01, open_ * (1 + rng.gauss(0.0003, 0.015)))
        high = max(open_, close) * (1 + abs(rng.gauss(0, 0.005)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, 0.005)))
        series[day.isoformat()] = {
            "1. open": f"{open_:.4f}",
            "2. high": f"{high:.4f}",
            "3. low": f"{low:.4f}",
            "4. close": f"{close:.4f}",
            "5. volume": str(rng.randint(100_000, 50_000_000)),
        }
        price = close
    return {
        "Meta Data": {"1. Information": "SYNTHETIC SAMPLE DATA", "2. Symbol": symbol},
        "Time Series (Daily)": series,
    }


def sample_fx_csv(start: date, end: date, seed: int = 42) -> str:
    rng = random.Random(f"{seed}-fx")
    rates = {"XUDLUSS": 1.27, "XUDLERS": 1.17}
    lines = ["DATE," + ",".join(BOE_SERIES)]
    for day in _trading_days(start, end):
        values = []
        for code in BOE_SERIES:
            rates[code] *= 1 + rng.gauss(0, 0.004)
            values.append(f"{rates[code]:.4f}")
        lines.append(day.strftime("%d %b %Y") + "," + ",".join(values))
    return "\n".join(lines)
