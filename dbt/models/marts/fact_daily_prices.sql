-- Grain: one row per instrument per trading day.
-- Prices are stored in the listing currency (GBX pence converted to GBP) and in GBP
-- using the Bank of England rate in force on that day.
with prices as (
    select * from {{ ref('stg_prices') }}
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
)

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
    close_local / lag(close_local) over (partition by symbol order by trade_date) - 1
                                                             as daily_return
from converted
