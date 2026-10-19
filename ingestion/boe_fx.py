"""Ingest daily sterling FX spot rates from the Bank of England Statistical Database."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

import requests

from ingestion.config import BOE_SERIES, BOE_URL


def fetch_fx_csv(start: date, timeout: int = 30) -> str:
    """Download a CSV of the configured series from `start` to today. No API key needed."""
    params = {
        "csv.x": "yes",
        "Datefrom": start.strftime("%d/%b/%Y"),
        "Dateto": "now",
        "SeriesCodes": ",".join(BOE_SERIES),
        "CSVF": "TN",  # tabular, no titles
        "UsingCodes": "Y",
        "VPD": "Y",
        "VFD": "N",
    }
    # The BoE site rejects requests without a browser-like user agent.
    headers = {"User-Agent": "Mozilla/5.0 (market-data-warehouse portfolio project)"}
    response = requests.get(BOE_URL, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _parse_boe_date(value: str) -> date:
    for fmt in ("%d %b %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised BoE date: {value!r}")


def parse_fx_csv(text: str, since: date | None = None) -> list[dict[str, Any]]:
    """Turn the wide BoE CSV (DATE, XUDLUSS, XUDLERS) into long rows: one per date and currency."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    rows = []
    for record in reader:
        rate_date = _parse_boe_date(record["DATE"])
        if since is not None and rate_date <= since:
            continue
        for series_code, currency in BOE_SERIES.items():
            raw = (record.get(series_code) or "").strip()
            if not raw:
                continue  # BoE leaves blanks on UK bank holidays
            rows.append(
                {
                    "rate_date": rate_date.isoformat(),
                    "currency_code": currency,
                    "series_code": series_code,
                    "units_per_gbp": float(raw),
                }
            )
    return sorted(rows, key=lambda r: (r["rate_date"], r["currency_code"]))
