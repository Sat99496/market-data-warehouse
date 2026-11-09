-- Grain: one row per instrument per trading day.
-- Prices are stored in the listing currency (GBX pence converted to GBP) and in GBP
-- using the Bank of England rate in force on that day.
--
-- Incremental: each run only rebuilds the last `fact_lookback_days` days (default 10),
-- so late-arriving prices or restated FX rates inside that window are picked up,
-- while older history is left alone. `dbt build --full-refresh` rebuilds everything
-- (do that after changing instrument reference data or this model's logic).
{{
    config(
        materialized='incremental',
        unique_key='price_key',
        incremental_strategy=('merge' if target.type == 'databricks' else 'delete+insert'),
        on_schema_change='fail'
    )
}}

{% set lookback_days = var('fact_lookback_days', 10) %}

with prices as (
    select * from {{ ref('stg_prices') }}
    {% if is_incremental() %}
    -- Read twice the window so lag() has the previous trading day for the first row we rewrite.
    where trade_date >= (
        select cast(max(trade_date) - interval {{ lookback_days * 2 }} day as date) from {{ this }}
    )
    {% endif %}
),

instrument as (
    select * from {{ ref('dim_instrument') }}
),

joined as (
    select
        prices.*,
        instrument.instrument_key,
        instrument.listing_currency,
        instrument.price_divisor
    from prices
    inner join instrument
        on instrument.symbol = prices.symbol
       and prices.trade_date >= instrument.valid_from
       and (instrument.valid_to is null or prices.trade_date < instrument.valid_to)
),

converted as (
    select
        joined.*,
        joined.close_quote / joined.price_divisor  as close_local,
        fx.units_per_gbp
    from joined
    left join {{ ref('int_fx_rates_daily') }} as fx
        on fx.date_day = joined.trade_date
       and fx.currency_code = joined.listing_currency
),

final as (
    select
        {{ surrogate_key(['symbol', 'trade_date']) }}            as price_key,
        {{ date_key('trade_date') }}                             as date_key,
        instrument_key,
        {{ surrogate_key(['listing_currency']) }}                as currency_key,
        symbol,
        trade_date,
        open_quote  / price_divisor                              as open_local,
        high_quote  / price_divisor                              as high_local,
        low_quote   / price_divisor                              as low_local,
        close_local,
        volume,
        units_per_gbp                                            as fx_units_per_gbp,
        close_local / units_per_gbp                              as close_gbp,
        close_local / units_per_gbp * volume                     as traded_value_gbp,
        -- Return in the listing currency (what a local investor sees).
        close_local / lag(close_local) over (partition by symbol order by trade_date) - 1
                                                                 as daily_return_local,
        -- Return in sterling (what a UK investor sees, including the currency move).
        (close_local / units_per_gbp)
          / lag(close_local / units_per_gbp) over (partition by symbol order by trade_date) - 1
                                                                 as daily_return_gbp
    from converted
)

select * from final
{% if is_incremental() %}
where trade_date >= (
    select cast(max(trade_date) - interval {{ lookback_days }} day as date) from {{ this }}
)
{% endif %}
