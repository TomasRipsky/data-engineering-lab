-- grain: one row per stint (one driver on one set of tyres in one session)
with source as (
    select * from {{ source('openf1', 'openf1_stints') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, stint_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    stint_number,
    lap_start as first_lap,
    lap_end as last_lap,
    coalesce(upper(compound), 'UNKNOWN') as compound,
    tyre_age_at_start,
    coalesce(lap_start <= lap_end, false) as has_valid_lap_range
from deduplicated
