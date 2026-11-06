-- Grain: one row per outlet, menu item and day.
select
    p.production_id,
    p.outlet_id,
    p.menu_id,
    to_char(p.production_date, 'YYYYMMDD')::integer as date_key,
    p.production_date,
    p.portions_forecast,
    p.portions_planned,
    p.portions_sold,
    p.portions_cooked,
    p.portions_wasted,
    round(p.portions_wasted::numeric / nullif(p.portions_cooked, 0), 4) as waste_rate,
    p.portions_cooked * m.food_cost_per_portion as cooked_food_cost,
    p.portions_wasted * m.food_cost_per_portion as wasted_food_cost
from {{ ref('production_logs') }} as p
join {{ ref('dim_menu_item') }} as m on m.menu_id = p.menu_id
