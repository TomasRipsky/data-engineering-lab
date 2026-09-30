-- grain: one row per lap of one driver in one Race or Sprint session
select
    laps.session_key,
    laps.meeting_key,
    laps.driver_number,
    laps.lap_number,
    laps.started_at,
    laps.ended_at,
    laps.lap_time_s,
    laps.sector_1_s,
    laps.sector_2_s,
    laps.sector_3_s,
    laps.speed_trap_kph,
    laps.stint_number,
    laps.compound,
    laps.tyre_age_laps,
    laps.is_pit_in_lap,
    laps.is_pit_out_lap,
    laps.neutralisation,
    laps.position_end_of_lap,
    laps.is_clean_lap
from {{ ref('int_laps_enriched') }} as laps
inner join {{ ref('dim_sessions') }} as sessions
    on sessions.session_key = laps.session_key
