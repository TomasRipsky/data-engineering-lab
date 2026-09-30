-- grain: one row per change in running order for one driver
with source as (
    select * from {{ source('openf1', 'openf1_position') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, date order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    date as recorded_at,
    position
from deduplicated
