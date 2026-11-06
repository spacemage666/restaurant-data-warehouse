-- Cost per portion = sum of (quantity x price) over the whole recipe.
-- food_cost_per_portion only counts food (raw materials and prepared items),
-- because packaging and gas are not thrown away when food is wasted.
with recipe_cost as (
    select
        r.menu_id,
        sum(r.qty_per_portion * i.price_per_unit) as cost_per_portion,
        sum(r.qty_per_portion * i.price_per_unit)
            filter (where i.category in ('raw_material', 'prepared')) as food_cost_per_portion
    from {{ ref('recipes') }} as r
    join {{ ref('ingredients') }} as i using (ingredient_id)
    group by r.menu_id
)

select
    m.menu_id,
    m.menu_name,
    m.category,
    m.price,
    round(c.cost_per_portion, 2) as cost_per_portion,
    round(c.food_cost_per_portion, 2) as food_cost_per_portion,
    round(m.price - c.cost_per_portion, 2) as gross_profit_per_portion,
    round((m.price - c.cost_per_portion) / m.price * 100, 1) as gross_margin_pct
from {{ ref('menu_items') }} as m
left join recipe_cost as c using (menu_id)
