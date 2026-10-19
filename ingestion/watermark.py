"""Simple file-based watermark store.

Keeps the latest date already ingested for each source key, so each daily run
only lands new records (idempotent, incremental ingestion).
On Azure this file is replaced by a small table or a JSON blob in ADLS.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class WatermarkStore:
    def __init__(self, path: Path):
        self.path = path
        self._marks: dict[str, str] = {}
        if path.exists():
            self._marks = json.loads(path.read_text())

    def get(self, key: str) -> date | None:
        value = self._marks.get(key)
        return date.fromisoformat(value) if value else None

    def set(self, key: str, value: date) -> None:
        current = self.get(key)
        # A watermark only ever moves forward, so replays can't rewind it.
        if current is None or value > current:
            self._marks[key] = value.isoformat()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._marks, indent=2, sort_keys=True))
