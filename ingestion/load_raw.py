"""Load every Bronze file into DuckDB `raw` tables for dbt to read.

Locally this stands in for the Bronze -> Silver step that Azure Databricks
will do in the cloud. Loads are a full rebuild from Bronze, so re-running is safe.
Deduplication happens in the dbt staging models.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from ingestion.config import BRONZE_DIR, WAREHOUSE_PATH


def load_raw(bronze_dir: Path = BRONZE_DIR, warehouse: Path = WAREHOUSE_PATH) -> dict[str, int]:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema if not exists raw")
        for dataset, table in (("prices", "raw.prices"), ("fx", "raw.fx")):
            pattern = str(bronze_dir / dataset / "*" / "*.jsonl")
            if not list((bronze_dir / dataset).glob("*/*.jsonl")):
                raise FileNotFoundError(f"No Bronze files for '{dataset}' under {bronze_dir}. Run ingestion first.")
            con.execute(
                f"""
                create or replace table {table} as
                select *, regexp_extract(filename, 'ingest_date=([0-9-]+)', 1)::date as _ingest_date
                from read_json_auto('{pattern}', filename = true, format = 'newline_delimited')
                """
            )
            counts[table] = con.execute(f"select count(*) from {table}").fetchone()[0]
    return counts
