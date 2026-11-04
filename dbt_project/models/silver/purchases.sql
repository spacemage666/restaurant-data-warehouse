select
    purchase_id,
    outlet_id,
    ingredient_id,
    purchase_date,
    purchase_type,
    quantity,
    unit_price,
    quantity * unit_price as total_cost,
    loaded_at
from {{ source('bronze', 'purchases') }}
