select
    ingredient_id,
    ingredient_name,
    category,
    storage,
    unit,
    shelf_life_days,
    thawed_shelf_life_days,
    is_perishable,
    price_per_unit
from {{ ref('ingredients') }}
