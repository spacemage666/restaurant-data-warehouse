-- Grain: one row per purchase.
select
    purchase_id,
    outlet_id,
    ingredient_id,
    to_char(purchase_date, 'YYYYMMDD')::integer as date_key,
    purchase_date,
    purchase_type,
    purchase_type = 'emergency' as is_emergency,
    quantity,
    unit_price,
    total_cost
from {{ ref('purchases') }}
