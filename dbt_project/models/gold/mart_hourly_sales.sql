select
    d.date_day,
    d.is_weekend,
    s.outlet_id,
    s.order_hour,
    sum(s.quantity) as portions,
    sum(s.line_total) as revenue
from {{ ref('fct_sales') }} as s
join {{ ref('dim_date') }} as d using (date_key)
group by 1, 2, 3, 4
