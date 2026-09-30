-- grain: one row per driver per Race or Sprint session
select
    drivers.session_key,
    drivers.driver_number,
    drivers.full_name,
    drivers.name_acronym,
    drivers.team_name,
    drivers.team_colour_hex
from {{ ref('stg_openf1__drivers') }} as drivers
inner join {{ ref('dim_sessions') }} as sessions
    on sessions.session_key = drivers.session_key
