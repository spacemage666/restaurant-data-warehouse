-- Grain: one row per waste record. waste_cost values the waste at the ingredient price.
select
    w.waste_id,
    w.outlet_id,
    w.ingredient_id,
    to_char(w.waste_date, 'YYYYMMDD')::integer as date_key,
    w.waste_date,
    w.reason,
    w.quantity,
    w.quantity * i.price_per_unit as waste_cost
from {{ ref('waste_logs') }} as w
join {{ ref('ingredients') }} as i using (ingredient_id)
