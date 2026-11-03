-- Bronze layer: raw copies of the generated CSV files.
-- No keys or constraints on purpose; validation happens in silver (dbt).
-- Some numeric columns are floats in the CSV (e.g. 90.0), so they use numeric.

CREATE TABLE IF NOT EXISTS bronze.outlets (
    outlet_id          integer,
    outlet_name        text,
    city               text,
    location_type      text,
    traffic_multiplier numeric(5, 2),
    loaded_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.ingredients (
    ingredient_id          integer,
    ingredient_name        text,
    category               text,
    storage                text,
    unit                   text,
    shelf_life_days        numeric(6, 1),
    thawed_shelf_life_days numeric(6, 1),
    price_per_unit         numeric(12, 3),
    loaded_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.menu_items (
    menu_id   integer,
    menu_name text,
    category  text,
    price     numeric(12, 2),
    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.recipes (
    menu_id         integer,
    ingredient_id   integer,
    qty_per_portion numeric(12, 3),
    loaded_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.orders (
    order_id  integer,
    outlet_id integer,
    order_ts  timestamp,
    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.order_items (
    order_id   integer,
    menu_id    integer,
    quantity   integer,
    unit_price numeric(12, 2),
    loaded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.production_logs (
    outlet_id          integer,
    menu_id            integer,
    production_date    date,
    portions_forecast  numeric(10, 1),
    portions_planned   integer,
    portions_sold      integer,
    portions_cooked    integer,
    portions_wasted    integer,
    loaded_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.purchases (
    purchase_id   integer,
    outlet_id     integer,
    ingredient_id integer,
    purchase_date date,
    purchase_type text,
    quantity      numeric(14, 1),
    unit_price    numeric(12, 3),
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.waste_logs (
    waste_id      integer,
    outlet_id     integer,
    ingredient_id integer,
    waste_date    date,
    reason        text,
    quantity      numeric(14, 1),
    loaded_at     timestamptz NOT NULL DEFAULT now()
);