-- grain: one row per session
with source as (
    select * from {{ source('openf1', 'openf1_sessions') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (partition by session_key order by _ingested_at desc) = 1
)

select
    session_key,
    meeting_key,
    session_type,
    session_name,
    year as season,
    date_start as starts_at,
    date_end as ends_at,
    coalesce(is_cancelled, false) as is_cancelled,
    circuit_short_name,
    country_name
from deduplicated
