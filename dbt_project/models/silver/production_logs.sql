select
    outlet_id::text || '-' || menu_id::text || '-' || production_date::text as production_id,
    outlet_id,
    menu_id,
    production_date,
    portions_forecast,
    portions_planned,
    portions_sold,
    portions_cooked,
    portions_wasted,
    loaded_at
from {{ source('bronze', 'production_logs') }}
