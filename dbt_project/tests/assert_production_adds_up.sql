-- Portions wasted must equal portions cooked minus portions sold.
select production_id
from {{ ref('production_logs') }}
where portions_wasted <> portions_cooked - portions_sold
   or portions_cooked < portions_sold
