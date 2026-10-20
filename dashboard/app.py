"""Market Data Warehouse - Streamlit dashboard over the dbt Gold layer.

Run:
    streamlit run dashboard/app.py

Reads only from the Gold star schema (gold.fact_daily_prices joined to its dimensions),
so it shows exactly what a BI tool or analyst would see.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = Path(os.getenv("MDW_WAREHOUSE", PROJECT_ROOT / "data" / "warehouse.duckdb"))

st.set_page_config(page_title="Market Data Warehouse", page_icon="📈", layout="wide")


@st.cache_data(ttl=600)
def load_prices(path: str) -> pd.DataFrame:
    query = """
        select
            f.trade_date,
            f.symbol,
            i.company_name,
            i.exchange,
            i.sector,
            i.listing_currency,
            f.close_local,
            f.close_gbp,
            f.fx_units_per_gbp,
            f.volume,
            f.traded_value_gbp,
            f.daily_return
        from gold.fact_daily_prices f
        join gold.dim_instrument i on i.instrument_key = f.instrument_key
        order by f.symbol, f.trade_date
    """
    with duckdb.connect(path, read_only=True) as con:
        df = con.execute(query).df()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def period_return(series: pd.Series) -> float:
    series = series.dropna()
    return float(series.iloc[-1] / series.iloc[0] - 1) if len(series) > 1 else float("nan")


# ---------- Load ----------
st.title("📈 Market Data Warehouse")
st.caption("US and London equities in sterling · Gold layer built with dbt · prices converted using Bank of England FX rates")

if not WAREHOUSE.exists():
    st.error(
        f"No warehouse found at `{WAREHOUSE}`.\n\n"
        "Build it first:\n\n"
        "```\npython -m ingestion.run --sample\ndbt build --project-dir dbt --profiles-dir dbt\n```"
    )
    st.stop()

prices = load_prices(str(WAREHOUSE))
if prices.empty:
    st.warning("The Gold tables are empty. Run ingestion and `dbt build` first.")
    st.stop()

# ---------- Filters ----------
with st.sidebar:
    st.header("Filters")
    labels = (
        prices[["symbol", "company_name"]].drop_duplicates()
        .assign(label=lambda d: d["symbol"] + " – " + d["company_name"])
        .set_index("symbol")["label"]
    )
    symbols = st.multiselect(
        "Instruments",
        options=list(labels.index),
        default=list(labels.index),
        format_func=lambda s: labels[s],
    )
    min_date, max_date = prices["trade_date"].min().date(), prices["trade_date"].max().date()
    default_start = max(min_date, max_date - timedelta(days=365))
    date_range = st.date_input("Date range", (default_start, max_date), min_value=min_date, max_value=max_date)
    st.divider()
    st.caption(f"Data to {max_date:%d %b %Y} · {prices['symbol'].nunique()} instruments")

if not symbols:
    st.info("Pick at least one instrument in the sidebar.")
    st.stop()

start, end = (date_range if isinstance(date_range, tuple) and len(date_range) == 2 else (default_start, max_date))
view = prices[
    prices["symbol"].isin(symbols)
    & prices["trade_date"].between(pd.Timestamp(start), pd.Timestamp(end))
].copy()

if view.empty:
    st.warning("No data for this selection.")
    st.stop()

# ---------- Summary per instrument ----------
summary = (
    view.sort_values("trade_date")
    .groupby(["symbol", "company_name", "listing_currency"], as_index=False)
    .agg(
        latest_gbp=("close_gbp", "last"),
        return_local=("close_local", period_return),
        return_gbp=("close_gbp", period_return),
        volatility=("daily_return", lambda r: r.std() * (252 ** 0.5)),
        traded_value_gbp=("traded_value_gbp", "sum"),
    )
)
summary["fx_impact"] = summary["return_gbp"] - summary["return_local"]

# ---------- KPI tiles ----------
best = summary.loc[summary["return_gbp"].idxmax()]
worst = summary.loc[summary["return_gbp"].idxmin()]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Instruments", len(summary))
c2.metric("Best performer (GBP)", best["symbol"], f"{best['return_gbp']:+.1%}")
c3.metric("Worst performer (GBP)", worst["symbol"], f"{worst['return_gbp']:+.1%}")
c4.metric("Traded value (GBP)", f"£{summary['traded_value_gbp'].sum() / 1e9:,.1f}bn")

# ---------- Tabs ----------
tab_perf, tab_fx, tab_data = st.tabs(["Performance", "Currency impact", "Data"])

with tab_perf:
    st.subheader("Growth of £100 invested")
    st.caption("Each instrument rebased to 100 on the first day of the selected period, in sterling.")
    pivot = view.pivot_table(index="trade_date", columns="symbol", values="close_gbp").sort_index()
    rebased = pivot.div(pivot.bfill().iloc[0]) * 100
    st.line_chart(rebased, height=380)

    st.subheader("Return, risk and liquidity")
    st.dataframe(
        summary[["symbol", "company_name", "latest_gbp", "return_gbp", "volatility", "traded_value_gbp"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "symbol": "Symbol",
            "company_name": "Company",
            "latest_gbp": st.column_config.NumberColumn("Latest price (£)", format="£%.2f"),
            "return_gbp": st.column_config.NumberColumn("Return (GBP)", format="percent"),
            "volatility": st.column_config.NumberColumn("Annualised volatility", format="percent"),
            "traded_value_gbp": st.column_config.NumberColumn("Traded value (£)", format="compact"),
        },
    )

with tab_fx:
    st.subheader("How much did currency moves add or remove?")
    st.caption(
        "For a UK investor, a US stock's return depends on both the share price and the USD/GBP rate. "
        "London-listed shares are already in sterling, so their currency impact is zero."
    )
    fx = summary[["symbol", "listing_currency", "return_local", "return_gbp", "fx_impact"]]
    st.bar_chart(
        (fx.set_index("symbol")["fx_impact"] * 100).rename("Currency impact (percentage points)"),
        height=300,
        x_label="Instrument",
        y_label="Currency impact (pp)",
    )
    st.dataframe(
        fx,
        hide_index=True,
        use_container_width=True,
        column_config={
            "symbol": "Symbol",
            "listing_currency": "Currency",
            "return_local": st.column_config.NumberColumn("Return (local)", format="percent"),
            "return_gbp": st.column_config.NumberColumn("Return (GBP)", format="percent"),
            "fx_impact": st.column_config.NumberColumn("Currency impact", format="percent"),
        },
    )

    usd = view[view["listing_currency"] == "USD"].drop_duplicates("trade_date").set_index("trade_date")
    if not usd.empty:
        st.subheader("USD per £1 (Bank of England)")
        st.line_chart(usd["fx_units_per_gbp"].rename("USD per GBP"), height=250)

with tab_data:
    st.subheader("Daily prices")
    st.dataframe(
        view.sort_values(["trade_date", "symbol"], ascending=[False, True]),
        hide_index=True,
        use_container_width=True,
    )
    st.download_button(
        "Download as CSV",
        view.to_csv(index=False).encode(),
        file_name="market_prices.csv",
        mime="text/csv",
    )
