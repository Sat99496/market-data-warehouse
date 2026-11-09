-- fact_daily_prices inner-joins prices to dim_instrument, so a ticker that is ingested
-- but missing from seeds/instruments.csv would silently disappear from the Gold layer.
-- This test fails instead, listing the symbols that need adding to the seed.
select distinct prices.symbol
from {{ ref('stg_prices') }} as prices
left join {{ ref('instruments') }} as instruments
    on instruments.symbol = prices.symbol
where instruments.symbol is null
