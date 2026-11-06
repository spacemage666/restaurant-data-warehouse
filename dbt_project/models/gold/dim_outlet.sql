select
    outlet_id,
    outlet_name,
    city,
    location_type,
    traffic_multiplier
from {{ ref('outlets') }}
