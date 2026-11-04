select
    outlet_id,
    outlet_name,
    city,
    lower(trim(location_type)) as location_type,
    traffic_multiplier,
    loaded_at
from {{ source('bronze', 'outlets') }}
