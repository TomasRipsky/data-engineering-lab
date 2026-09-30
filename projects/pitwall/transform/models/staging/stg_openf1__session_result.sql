-- grain: one row per driver per finished session
with source as (
    select * from {{ source('openf1', 'openf1_session_result') }}
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
    position as finish_position,
    number_of_laps as laps_completed,
    points,
    coalesce(dnf, false) as did_not_finish,
    coalesce(dns, false) as did_not_start,
    coalesce(dsq, false) as disqualified,
    gap_to_leader
from deduplicated
