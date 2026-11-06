-- Grain: one row per menu item within an order.
select
    oi.order_item_id,
    oi.order_id,
    o.outlet_id,
    oi.menu_id,
    to_char(o.order_date, 'YYYYMMDD')::integer as date_key,
    o.order_ts,
    o.order_hour,
    oi.quantity,
    oi.unit_price,
    oi.line_total,
    oi.quantity * m.cost_per_portion as cost_total,
    oi.line_total - oi.quantity * m.cost_per_portion as gross_profit
from {{ ref('order_items') }} as oi
join {{ ref('orders') }} as o using (order_id)
join {{ ref('dim_menu_item') }} as m on m.menu_id = oi.menu_id
