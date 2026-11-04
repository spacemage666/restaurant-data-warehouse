select
    order_id::text || '-' || menu_id::text as order_item_id,
    order_id,
    menu_id,
    quantity,
    unit_price,
    quantity * unit_price as line_total,
    loaded_at
from {{ source('bronze', 'order_items') }}
