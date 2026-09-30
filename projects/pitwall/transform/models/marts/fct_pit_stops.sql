-- grain: one row per pit stop
with pits as (
    select * from {{ ref('stg_openf1__pit') }}
),

stints as (
    select * from {{ ref('stg_openf1__stints') }}
),

laps as (
    select session_key, driver_number, lap_number, position_end_of_lap, neutralisation
    from {{ ref('int_laps_enriched') }}
),

sessions_with_pit_data as (
    select distinct session_key from pits
),

inferred as (
    -- no pit data for the whole session (e.g. some 2023 races): a tyre change means a stop
    select
        this_stint.session_key,
        this_stint.meeting_key,
        this_stint.driver_number,
        this_stint.last_lap as lap_number
    from stints as this_stint
    inner join stints as next_stint
        on next_stint.session_key = this_stint.session_key
        and next_stint.driver_number = this_stint.driver_number
        and next_stint.stint_number = this_stint.stint_number + 1
    where this_stint.session_key not in (select session_key from sessions_with_pit_data)
),

stops as (
    select
        session_key, meeting_key, driver_number, lap_number,
        pit_lane_time_s, stationary_time_s, 'pit' as source
    from pits
    union all
    select
        session_key, meeting_key, driver_number, lap_number,
        cast(null as float64), cast(null as float64), 'stint_change'
    from inferred
)

select
    stops.session_key,
    stops.meeting_key,
    stops.driver_number,
    stops.lap_number,
    stops.pit_lane_time_s,
    stops.stationary_time_s,
    stops.source,
    before_stop.compound as compound_before,
    after_stop.compound as compound_after,
    lap_before.position_end_of_lap as position_before,
    lap_after.position_end_of_lap as position_after,
    in_lap.neutralisation is not null as is_under_neutralisation
from stops
left join stints as before_stop
    on before_stop.session_key = stops.session_key
    and before_stop.driver_number = stops.driver_number
    and stops.lap_number between before_stop.first_lap and before_stop.last_lap
left join stints as after_stop
    on after_stop.session_key = stops.session_key
    and after_stop.driver_number = stops.driver_number
    and after_stop.first_lap = stops.lap_number + 1
left join laps as lap_before
    on lap_before.session_key = stops.session_key
    and lap_before.driver_number = stops.driver_number
    and lap_before.lap_number = stops.lap_number - 1
left join laps as lap_after
    on lap_after.session_key = stops.session_key
    and lap_after.driver_number = stops.driver_number
    and lap_after.lap_number = stops.lap_number + 1
left join laps as in_lap
    on in_lap.session_key = stops.session_key
    and in_lap.driver_number = stops.driver_number
    and in_lap.lap_number = stops.lap_number
where true
qualify row_number() over (
    partition by stops.session_key, stops.driver_number, stops.lap_number
    order by before_stop.stint_number desc, after_stop.stint_number
) = 1
