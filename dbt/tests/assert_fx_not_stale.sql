-- A rate carried forward for more than 5 days means the FX feed has probably stopped.
-- Flags any run of carried-forward rates longer than that.
with flagged as (
    select
        currency_code,
        date_day,
        is_carried_forward,
        sum(case when is_carried_forward then 0 else 1 end)
            over (partition by currency_code order by date_day) as publish_group
    from {{ ref('int_fx_rates_daily') }}
    where currency_code <> 'GBP'
)

select currency_code, publish_group, count(*) as days_carried
from flagged
where is_carried_forward
group by currency_code, publish_group
having count(*) > 5
