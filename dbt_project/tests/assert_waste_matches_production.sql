-- The value of overproduction waste (ingredient level) must match the value of
-- wasted portions (production level), allowing 0.1% for rounding.
with totals as (
    select
        (select sum(waste_cost) from {{ ref('fct_waste') }} where reason = 'overproduction') as waste_value,
        (select sum(wasted_food_cost) from {{ ref('fct_production') }}) as production_value
)

select *
from totals
where abs(waste_value - production_value) > 0.001 * production_value
