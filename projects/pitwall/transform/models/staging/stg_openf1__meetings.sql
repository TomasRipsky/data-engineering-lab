-- grain: one row per meeting (race weekend)
with source as (
    select * from {{ source('openf1', 'openf1_meetings') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (partition by meeting_key order by _ingested_at desc) = 1
)

select
    meeting_key,
    meeting_name,
    meeting_official_name,
    year as season,
    location,
    country_name,
    circuit_short_name,
    circuit_type,
    date_start as starts_at,
    date_end as ends_at
from deduplicated
