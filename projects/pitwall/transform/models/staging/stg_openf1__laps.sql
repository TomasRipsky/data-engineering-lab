-- grain: one row per lap of one driver in one session
with source as (
    select * from {{ source('openf1', 'openf1_laps') }}
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
    date_start as started_at,
    lap_duration as lap_time_s,
    duration_sector_1 as sector_1_s,
    duration_sector_2 as sector_2_s,
    duration_sector_3 as sector_3_s,
    st_speed as speed_trap_kph,
    coalesce(is_pit_out_lap, false) as is_pit_out_lap
from deduplicated
