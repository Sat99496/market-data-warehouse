"""Unit tests for the ingestion layer. Run with: pytest"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from ingestion import alpha_vantage, boe_fx
from ingestion.sample_data import sample_daily_payload, sample_fx_csv
from ingestion.watermark import WatermarkStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------- Alpha Vantage ----------

def test_parse_daily_flattens_and_sorts():
    payload = sample_daily_payload("AAPL", date(2026, 1, 5), date(2026, 1, 9))
    rows = alpha_vantage.parse_daily(payload)
    assert [r["trade_date"] for r in rows] == ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
    assert set(rows[0]) == {"symbol", "trade_date", "open", "high", "low", "close", "volume"}
    assert all(r["symbol"] == "AAPL" for r in rows)


def test_parse_daily_keeps_only_days_after_watermark():
    payload = sample_daily_payload("MSFT", date(2026, 1, 5), date(2026, 1, 9))
    rows = alpha_vantage.parse_daily(payload, since=date(2026, 1, 7))
    assert [r["trade_date"] for r in rows] == ["2026-01-08", "2026-01-09"]


def test_sample_data_skips_weekends():
    payload = sample_daily_payload("NVDA", date(2026, 1, 9), date(2026, 1, 12))  # Fri -> Mon
    assert list(payload["Time Series (Daily)"]) == ["2026-01-09", "2026-01-12"]


@pytest.mark.parametrize("error_key", ["Error Message", "Note", "Information"])
def test_fetch_daily_raises_on_api_error_body(monkeypatch, error_key):
    """Alpha Vantage returns HTTP 200 for rate limits and bad symbols - we must not treat that as data."""

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {error_key: "rate limit reached"}

    monkeypatch.setattr(alpha_vantage.requests, "get", lambda *a, **k: FakeResponse())
    with pytest.raises(alpha_vantage.AlphaVantageError):
        alpha_vantage.fetch_daily("AAPL", api_key="demo")


# ---------- Bank of England FX ----------

def test_parse_fx_csv_is_long_format_and_skips_blanks():
    text = "DATE,XUDLUSS,XUDLERS\n02 Jan 2026,1.2700,1.1700\n05 Jan 2026,1.2750,\n"
    rows = boe_fx.parse_fx_csv(text)
    assert rows == [
        {"rate_date": "2026-01-02", "currency_code": "EUR", "series_code": "XUDLERS", "units_per_gbp": 1.17},
        {"rate_date": "2026-01-02", "currency_code": "USD", "series_code": "XUDLUSS", "units_per_gbp": 1.27},
        {"rate_date": "2026-01-05", "currency_code": "USD", "series_code": "XUDLUSS", "units_per_gbp": 1.275},
    ]


def test_parse_fx_csv_respects_watermark():
    text = sample_fx_csv(date(2026, 1, 5), date(2026, 1, 9))
    rows = boe_fx.parse_fx_csv(text, since=date(2026, 1, 8))
    assert {r["rate_date"] for r in rows} == {"2026-01-09"}


# ---------- Watermarks ----------

def test_watermark_only_moves_forward(tmp_path):
    store = WatermarkStore(tmp_path / "wm.json")
    store.set("prices:AAPL", date(2026, 3, 1))
    store.set("prices:AAPL", date(2026, 2, 1))  # a replay of older data must not rewind it
    store.save()
    assert WatermarkStore(tmp_path / "wm.json").get("prices:AAPL") == date(2026, 3, 1)


# ---------- End to end ----------

def _run_ingestion(data_dir: Path) -> None:
    env = {**os.environ, "MDW_DATA_DIR": str(data_dir)}
    subprocess.run([sys.executable, "-m", "ingestion.run", "--sample"], cwd=PROJECT_ROOT, env=env, check=True)


def test_rerun_is_incremental_and_idempotent(tmp_path):
    """Second run on the same day finds no new data and lands no duplicate files."""
    _run_ingestion(tmp_path)
    files_after_first = sorted(p.relative_to(tmp_path) for p in (tmp_path / "bronze").rglob("*.jsonl"))
    _run_ingestion(tmp_path)
    files_after_second = sorted(p.relative_to(tmp_path) for p in (tmp_path / "bronze").rglob("*.jsonl"))

    assert files_after_first == files_after_second
    marks = json.loads((tmp_path / "state" / "watermarks_sample.json").read_text())
    assert "fx" in marks and "prices:AAPL" in marks
    assert (tmp_path / "warehouse.duckdb").exists()
