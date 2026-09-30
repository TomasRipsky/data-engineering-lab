-- grain: one row per race-control message
with source as (
    select * from {{ source('openf1', 'openf1_race_control') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, date, message, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    date as recorded_at,
    lap_number,
    driver_number,
    category,
    flag,
    message
from deduplicated
