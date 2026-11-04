select
    waste_id,
    outlet_id,
    ingredient_id,
    waste_date,
    reason,
    quantity,
    loaded_at
from {{ source('bronze', 'waste_logs') }}
