-- Total revenue must be identical in silver, the fact table and the sales mart.
with totals as (
    select
        (select sum(line_total) from {{ ref('order_items') }}) as silver_revenue,
        (select sum(line_total) from {{ ref('fct_sales') }}) as fact_revenue,
        (select sum(revenue) from {{ ref('mart_daily_sales') }}) as mart_revenue
)

select *
from totals
where silver_revenue <> fact_revenue
   or silver_revenue <> mart_revenue
