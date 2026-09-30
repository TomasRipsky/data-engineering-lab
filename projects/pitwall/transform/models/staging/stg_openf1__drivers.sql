-- grain: one row per driver per session
with source as (
    select * from {{ source('openf1', 'openf1_drivers') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    full_name,
    name_acronym,
    team_name,
    concat('#', team_colour) as team_colour_hex
from deduplicated
