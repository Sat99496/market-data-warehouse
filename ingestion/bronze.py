"""Write raw records to the Bronze layer as JSON Lines, partitioned by ingest date.

Layout (local disk now, ADLS Gen2 later):
    bronze/prices/ingest_date=2026-10-19/AAPL.jsonl
    bronze/fx/ingest_date=2026-10-19/fx.jsonl
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def write_jsonl(base_dir: Path, dataset: str, name: str, rows: Iterable[dict[str, Any]], ingest_date: date) -> Path | None:
    rows = list(rows)
    if not rows:
        return None
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    folder = base_dir / dataset / f"ingest_date={ingest_date.isoformat()}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name.replace('/', '_')}.jsonl"
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps({**row, "_ingested_at": ingested_at}) + "\n")
    return path
