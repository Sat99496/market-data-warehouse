select
    {{ surrogate_key(['currency_code']) }} as currency_key,
    currency_code,
    currency_name,
    boe_series_code
from {{ ref('currencies') }}
