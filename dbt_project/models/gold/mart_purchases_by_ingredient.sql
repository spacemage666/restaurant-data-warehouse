select
    d.date_day,
    p.outlet_id,
    o.outlet_name,
    o.location_type,
    p.ingredient_id,
    i.ingredient_name,
    i.category as ingredient_category,
    p.purchase_type,
    p.quantity,
    p.total_cost
from {{ ref('fct_purchases') }} as p
join {{ ref('dim_date') }} as d using (date_key)
join {{ ref('dim_outlet') }} as o on o.outlet_id = p.outlet_id
join {{ ref('dim_ingredient') }} as i on i.ingredient_id = p.ingredient_id
