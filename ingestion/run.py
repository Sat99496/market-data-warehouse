"""Command-line entry point for ingestion.

Examples
--------
Run everything offline with synthetic data (no API key, no network):
    python -m ingestion.run --sample

First real run - ignores watermarks and pulls everything the API offers
(latest ~100 trading days on the free tier; full history on a premium key):
    python -m ingestion.run --backfill

Daily incremental run - only new days since each watermark:
    python -m ingestion.run
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import date, timedelta

import requests

from ingestion import alpha_vantage, boe_fx, sample_data
from ingestion.bronze import write_jsonl
from ingestion.config import AV_FULL_HISTORY, AV_SLEEP_SECONDS, BRONZE_DIR, STATE_DIR, TICKERS
from ingestion.load_raw import load_raw
from ingestion.watermark import WatermarkStore

log = logging.getLogger("ingestion")


def ingest_prices(store: WatermarkStore, today: date, sample: bool, backfill: bool) -> int:
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not sample and not api_key:
        raise SystemExit("Set ALPHA_VANTAGE_API_KEY (see .env.example) or run with --sample.")
    total, failed = 0, []
    for i, symbol in enumerate(TICKERS):
        key = f"prices:{symbol}"
        since = None if backfill else store.get(key)
        if sample:
            payload = sample_data.sample_daily_payload(symbol, today - timedelta(days=730), today)
        else:
            if i:
                time.sleep(AV_SLEEP_SECONDS)  # free tier: 5 requests/minute
            want_full = AV_FULL_HISTORY and (backfill or since is None)
            try:
                payload = alpha_vantage.fetch_daily(symbol, api_key, full_history=want_full)
            except (alpha_vantage.AlphaVantageError, requests.RequestException) as exc:
                # One bad symbol must not stop the others; its watermark stays put, so the next run retries it.
                log.error("prices %-9s FAILED: %s", symbol, exc)
                failed.append(symbol)
                continue
        rows = alpha_vantage.parse_daily(payload, since=since)
        write_jsonl(BRONZE_DIR, "prices", symbol, rows, today)
        if rows:
            store.set(key, date.fromisoformat(rows[-1]["trade_date"]))
        log.info("prices %-9s new rows: %d", symbol, len(rows))
        total += len(rows)
    if failed:
        log.warning("%d of %d symbols failed and will be retried next run: %s", len(failed), len(TICKERS), ", ".join(failed))
        if len(failed) == len(TICKERS):
            raise SystemExit("Every symbol failed - check your API key and the daily request limit (25/day on the free tier).")
    return total


def ingest_fx(store: WatermarkStore, today: date, sample: bool, backfill: bool) -> int:
    since = None if backfill else store.get("fx")
    start = since or (today - timedelta(days=730))
    text = sample_data.sample_fx_csv(start, today) if sample else boe_fx.fetch_fx_csv(start)
    rows = boe_fx.parse_fx_csv(text, since=since)
    write_jsonl(BRONZE_DIR, "fx", "fx", rows, today)
    if rows:
        store.set("fx", date.fromisoformat(rows[-1]["rate_date"]))
    log.info("fx new rows: %d", len(rows))
    return len(rows)


def load_dotenv(path: str = ".env") -> None:
    """Read KEY=value lines from .env into the environment (no extra dependency needed)."""
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ingest prices and FX into the Bronze layer, then load DuckDB raw tables.")
    parser.add_argument("--sample", action="store_true", help="use synthetic data (offline)")
    parser.add_argument("--backfill", action="store_true", help="ignore watermarks and pull full history")
    parser.add_argument("--skip-load", action="store_true", help="only write Bronze files")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    today = date.today()
    store = WatermarkStore(STATE_DIR / ("watermarks_sample.json" if args.sample else "watermarks.json"))
    ingest_prices(store, today, args.sample, args.backfill)
    ingest_fx(store, today, args.sample, args.backfill)
    store.save()

    if not args.skip_load:
        for table, count in load_raw().items():
            log.info("loaded %s: %d rows", table, count)


if __name__ == "__main__":
    main()
