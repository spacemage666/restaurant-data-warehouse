select
    menu_id::text || '-' || ingredient_id::text as recipe_id,
    menu_id,
    ingredient_id,
    qty_per_portion,
    loaded_at
from {{ source('bronze', 'recipes') }}
