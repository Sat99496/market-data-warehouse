-- One row per published date and currency (Bank of England business days only).
with source as (
    select * from {{ source('raw', 'fx') }}
),

typed as (
    select
        cast(rate_date as date)          as rate_date,
        cast(currency_code as varchar)   as currency_code,
        cast(series_code as varchar)     as series_code,
        cast(units_per_gbp as double)    as units_per_gbp,
        cast(_ingested_at as timestamp)  as ingested_at,
        row_number() over (
            partition by rate_date, currency_code
            order by cast(_ingested_at as timestamp) desc, _ingest_date desc
        ) as row_num
    from source
)

select rate_date, currency_code, series_code, units_per_gbp, ingested_at
from typed
where row_num = 1
