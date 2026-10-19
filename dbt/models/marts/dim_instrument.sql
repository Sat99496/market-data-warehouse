-- SCD Type 2 instrument dimension built from the snapshot.
-- The first version of each instrument is back-dated to 1900-01-01 so that historical
-- prices loaded before the first snapshot still join to a valid version.
with versions as (
    select
        *,
        row_number() over (partition by symbol order by dbt_valid_from) as version_number
    from {{ ref('instruments_snapshot') }}
)

select
    {{ surrogate_key(['symbol', 'dbt_valid_from']) }} as instrument_key,
    symbol,
    company_name,
    exchange,
    listing_currency,
    quote_unit,
    price_divisor,
    sector,
    version_number,
    case when version_number = 1 then cast('1900-01-01' as date)
         else cast(dbt_valid_from as date) end       as valid_from,
    cast(dbt_valid_to as date)                       as valid_to,
    dbt_valid_to is null                             as is_current
from versions
