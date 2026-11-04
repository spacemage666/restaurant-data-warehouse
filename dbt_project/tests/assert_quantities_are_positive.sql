-- Returns rows that break the rule; the test passes when no rows come back.
select 'purchases' as source_table, purchase_id::text as record_id
from {{ ref('purchases') }}
where quantity <= 0

union all

select 'waste_logs', waste_id::text
from {{ ref('waste_logs') }}
where quantity <= 0
