"""Smoke test: the dashboard renders against a built warehouse without errors.

Skipped when no warehouse exists yet; CI runs it after `dbt build`.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = Path(os.getenv("MDW_WAREHOUSE", PROJECT_ROOT / "data" / "warehouse.duckdb"))

pytestmark = pytest.mark.skipif(not WAREHOUSE.exists(), reason="build the warehouse first (ingestion + dbt build)")


def test_dashboard_renders():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"), default_timeout=60).run()

    assert not app.exception, app.exception
    assert len(app.metric) == 4
    assert app.metric[0].value != "0"
    assert len(app.tabs) == 3
