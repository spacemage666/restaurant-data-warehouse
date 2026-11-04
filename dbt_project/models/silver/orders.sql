select
    order_id,
    outlet_id,
    order_ts,
    order_ts::date as order_date,
    extract(hour from order_ts)::integer as order_hour,
    loaded_at
from {{ source('bronze', 'orders') }}
