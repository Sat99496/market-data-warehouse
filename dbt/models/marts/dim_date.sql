-- Calendar dimension covering every day that has prices.
with bounds as (
    select min(trade_date) as start_date, max(trade_date) as end_date
    from {{ ref('stg_prices') }}
),

days as (
    {{ date_series('(select start_date from bounds)', '(select end_date from bounds)') }}
)

select
    {{ date_key('date_day') }}                    as date_key,
    date_day                                      as calendar_date,
    year(date_day)                                as calendar_year,
    quarter(date_day)                             as calendar_quarter,
    month(date_day)                               as calendar_month,
    {{ month_name('date_day') }}                  as month_name,
    {{ iso_day_of_week('date_day') }}             as iso_day_of_week,
    {{ day_name('date_day') }}                    as day_name,
    {{ iso_day_of_week('date_day') }} >= 6        as is_weekend
from days
