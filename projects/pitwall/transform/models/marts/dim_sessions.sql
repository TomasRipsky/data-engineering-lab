-- grain: one row per Race or Sprint session with lap data
with sessions as (
    select * from {{ ref('stg_openf1__sessions') }}
),

sessions_with_laps as (
    select distinct session_key from {{ ref('stg_openf1__laps') }}
)

select
    sessions.session_key,
    sessions.meeting_key,
    sessions.session_name,
    sessions.season,
    sessions.starts_at,
    sessions.ends_at,
    sessions.circuit_short_name,
    sessions.country_name
from sessions
inner join sessions_with_laps
    on sessions_with_laps.session_key = sessions.session_key
where sessions.session_type = 'Race'
    and not sessions.is_cancelled
