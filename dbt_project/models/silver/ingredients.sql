select
    ingredient_id,
    ingredient_name,
    category,
    storage,
    unit,
    shelf_life_days::integer as shelf_life_days,
    thawed_shelf_life_days::integer as thawed_shelf_life_days,
    price_per_unit,
    shelf_life_days is not null as is_perishable,
    loaded_at
from {{ source('bronze', 'ingredients') }}
