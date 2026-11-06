select
    d.date_day,
    p.outlet_id,
    o.outlet_name,
    o.location_type,
    p.menu_id,
    m.menu_name,
    p.portions_forecast,
    p.portions_planned,
    p.portions_sold,
    p.portions_cooked,
    p.portions_wasted,
    p.cooked_food_cost,
    p.wasted_food_cost
from {{ ref('fct_production') }} as p
join {{ ref('dim_date') }} as d using (date_key)
join {{ ref('dim_outlet') }} as o on o.outlet_id = p.outlet_id
join {{ ref('dim_menu_item') }} as m on m.menu_id = p.menu_id
