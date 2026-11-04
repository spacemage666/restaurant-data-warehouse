select
    menu_id,
    menu_name,
    category,
    price::integer as price,
    loaded_at
from {{ source('bronze', 'menu_items') }}
