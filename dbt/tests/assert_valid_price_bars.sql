-- Every price must be positive and each daily bar must be internally consistent:
-- low <= open, close <= high. Returns the offending rows (test passes when empty).
select symbol, trade_date, open_local, high_local, low_local, close_local
from {{ ref('fact_daily_prices') }}
where close_local <= 0
   or low_local  <= 0
   or high_local < low_local
   or open_local  not between low_local and high_local
   or close_local not between low_local and high_local
