with all_dates as (
    select order_date as d from {{ ref('orders') }}
    union all
    select production_date from {{ ref('production_logs') }}
    union all
    select purchase_date from {{ ref('purchases') }}
    union all
    select waste_date from {{ ref('waste_logs') }}
),

bounds as (
    select min(d) as first_date, max(d) as last_date
    from all_dates
),

calendar as (
    select generate_series(first_date, last_date, interval '1 day')::date as date_day
    from bounds
)

select
    to_char(date_day, 'YYYYMMDD')::integer as date_key,
    date_day,
    extract(year from date_day)::integer as year,
    extract(month from date_day)::integer as month,
    to_char(date_day, 'FMMonth') as month_name,
    extract(isodow from date_day)::integer as day_of_week,
    to_char(date_day, 'FMDay') as day_name,
    extract(week from date_day)::integer as week_of_year,
    extract(isodow from date_day) >= 6 as is_weekend
from calendar
