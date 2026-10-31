with daily as (
    select
        symbol,
        trade_date,
        close_gbp,
        cast(date_trunc('month', trade_date) as date) as month_start
    from {{ ref('fact_daily_prices') }}
),

ranked as (
    select
        *,
        row_number() over (partition by symbol, month_start order by trade_date)      as first_day,
        row_number() over (partition by symbol, month_start order by trade_date desc) as last_day
    from daily
)

select
    symbol,
    month_start,
    count(*)                                              as trading_days,
    round(avg(close_gbp), 2)                              as avg_close_gbp,
    max(case when first_day = 1 then close_gbp end)       as first_close_gbp,
    max(case when last_day = 1 then close_gbp end)        as last_close_gbp,
    max(case when last_day = 1 then close_gbp end)
      / max(case when first_day = 1 then close_gbp end) - 1 as monthly_return
from ranked
group by symbol, month_start