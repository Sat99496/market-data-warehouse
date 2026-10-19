-- One row per symbol and trading day.
-- If the same day was ingested more than once (a replay or a backfill), keep the latest copy.
with source as (
    select * from {{ source('raw', 'prices') }}
),

typed as (
    select
        cast(symbol as varchar)          as symbol,
        cast(trade_date as date)         as trade_date,
        cast(open as double)             as open_quote,
        cast(high as double)             as high_quote,
        cast(low as double)              as low_quote,
        cast(close as double)            as close_quote,
        cast(volume as bigint)           as volume,
        cast(_ingested_at as timestamp)  as ingested_at,
        row_number() over (
            partition by symbol, trade_date
            order by cast(_ingested_at as timestamp) desc, _ingest_date desc
        ) as row_num
    from source
)

select
    symbol,
    trade_date,
    open_quote,
    high_quote,
    low_quote,
    close_quote,
    volume,
    ingested_at
from typed
where row_num = 1
