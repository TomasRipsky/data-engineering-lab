-- grain: one row per driver per starting grid (keyed by the qualifying session that set it)
with source as (
    select * from {{ source('openf1', 'openf1_starting_grid') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key as qualifying_session_key,
    meeting_key,
    driver_number,
    position as grid_position,
    lap_duration as qualifying_lap_time_s
from deduplicated
