-- grain: one row per pit-lane visit
with source as (
    select * from {{ source('openf1', 'openf1_pit') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, lap_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    lap_number,
    date as pitted_at,
    coalesce(lane_duration, pit_duration) as pit_lane_time_s,
    stop_duration as stationary_time_s
from deduplicated
