-- Every calendar day x every currency, with the most recent published rate carried forward.
-- Needed because markets trade on days the Bank of England does not publish (and vice versa).
-- GBP is added with a rate of 1 so sterling prices join the same way as foreign ones.
with bounds as (
    select min(rate_date) as start_date, current_date as end_date
    from {{ ref('stg_fx_rates') }}
),

calendar as (
    {{ date_series('(select start_date from bounds)', '(select end_date from bounds)') }}
),

currencies as (
    select distinct currency_code from {{ ref('stg_fx_rates') }}
),

grid as (
    select calendar.date_day, currencies.currency_code
    from calendar
    cross join currencies
),

filled as (
    select
        grid.date_day,
        grid.currency_code,
        fx.units_per_gbp as published_rate,
        {{ forward_fill('fx.units_per_gbp', 'grid.currency_code', 'grid.date_day') }} as units_per_gbp
    from grid
    left join {{ ref('stg_fx_rates') }} as fx
        on fx.rate_date = grid.date_day
       and fx.currency_code = grid.currency_code
)

select
    date_day,
    currency_code,
    units_per_gbp,
    published_rate is null as is_carried_forward
from filled
where units_per_gbp is not null

union all

select date_day, 'GBP' as currency_code, 1.0 as units_per_gbp, false as is_carried_forward
from calendar
