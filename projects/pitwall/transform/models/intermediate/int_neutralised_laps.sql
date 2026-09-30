-- grain: one row per session, lap and neutralisation type (SC or VSC)
with messages as (
    select
        session_key,
        recorded_at,
        lap_number,
        case message
            when 'SAFETY CAR DEPLOYED' then 'SC'
            when 'VIRTUAL SAFETY CAR DEPLOYED' then 'VSC'
        end as started,
        case message
            when 'SAFETY CAR IN THIS LAP' then 'SC'
            when 'VIRTUAL SAFETY CAR ENDING' then 'VSC'
        end as ended
    from {{ ref('stg_openf1__race_control') }}
    where category = 'SafetyCar'
),

starts as (
    select
        session_key,
        started as neutralisation,
        recorded_at,
        lap_number as first_lap,
        lead(recorded_at) over (
            partition by session_key, started order by recorded_at
        ) as next_start_at,
        lead(lap_number) over (
            partition by session_key, started order by recorded_at
        ) as next_start_lap
    from messages
    where started is not null
),

ends as (
    select session_key, ended as neutralisation, recorded_at, lap_number
    from messages
    where ended is not null
),

last_laps as (
    select session_key, max(lap_number) as last_lap
    from {{ ref('stg_openf1__laps') }}
    group by session_key
),

periods as (
    select
        starts.session_key,
        starts.neutralisation,
        starts.first_lap,
        coalesce(
            min(ends.lap_number),
            any_value(starts.next_start_lap) - 1,
            any_value(last_laps.last_lap)
        ) as last_lap
    from starts
    left join ends
        on ends.session_key = starts.session_key
        and ends.neutralisation = starts.neutralisation
        and ends.recorded_at > starts.recorded_at
        and ends.recorded_at < coalesce(starts.next_start_at, timestamp '9999-12-31')
    left join last_laps
        on last_laps.session_key = starts.session_key
    group by starts.session_key, starts.neutralisation, starts.first_lap, starts.recorded_at
)

select distinct
    periods.session_key,
    lap_number,
    periods.neutralisation
from periods
cross join unnest(generate_array(periods.first_lap, periods.last_lap)) as lap_number
