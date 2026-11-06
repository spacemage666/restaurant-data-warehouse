select
    d.date_day,
    w.outlet_id,
    o.outlet_name,
    o.location_type,
    w.ingredient_id,
    i.ingredient_name,
    i.category as ingredient_category,
    w.reason,
    w.quantity,
    w.waste_cost
from {{ ref('fct_waste') }} as w
join {{ ref('dim_date') }} as d using (date_key)
join {{ ref('dim_outlet') }} as o on o.outlet_id = w.outlet_id
join {{ ref('dim_ingredient') }} as i on i.ingredient_id = w.ingredient_id
