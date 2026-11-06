select
    d.date_day,
    d.is_weekend,
    s.outlet_id,
    o.outlet_name,
    o.city,
    o.location_type,
    s.menu_id,
    m.menu_name,
    count(distinct s.order_id) as orders,
    sum(s.quantity) as portions,
    sum(s.line_total) as revenue,
    sum(s.cost_total) as cost_total,
    sum(s.gross_profit) as gross_profit
from {{ ref('fct_sales') }} as s
join {{ ref('dim_date') }} as d using (date_key)
join {{ ref('dim_outlet') }} as o on o.outlet_id = s.outlet_id
join {{ ref('dim_menu_item') }} as m on m.menu_id = s.menu_id
group by 1, 2, 3, 4, 5, 6, 7, 8
