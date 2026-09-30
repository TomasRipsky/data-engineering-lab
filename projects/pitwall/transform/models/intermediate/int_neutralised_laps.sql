-- grain: one row per session, lap and neutralisation type (SC, VSC or RED)
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
        end as ended,
        coalesce(flag = 'RED', false) as is_red_flag
    from {{ ref('stg_openf1__race_control') }}
    where category = 'SafetyCar' or flag = 'RED'
),

starts as (
    select session_key, started as neutralisation, recorded_at, lap_number as first_lap
    from messages
    where started is not null
),

ends as (
    select session_key, ended as neutralisation, recorded_at, lap_number
    from messages
    where ended is not null
),

-- anything that interrupts a period: a red flag or a new deployment of either type
interruptions as (
    select session_key, recorded_at, lap_number, is_red_flag
    from messages
    where started is not null or is_red_flag
),

next_interruption as (
    select
        starts.session_key,
        starts.neutralisation,
        starts.recorded_at,
        interruptions.recorded_at as interrupted_at,
        -- the red-flag lap still belongs to the period; a new deployment starts its own lap
        if(
            interruptions.is_red_flag, interruptions.lap_number, interruptions.lap_number - 1
        ) as capped_last_lap
    from starts
    inner join interruptions
        on interruptions.session_key = starts.session_key
        and interruptions.recorded_at > starts.recorded_at
    where true
    qualify row_number() over (
        partition by starts.session_key, starts.neutralisation, starts.recorded_at
        order by interruptions.recorded_at
    ) = 1
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
            any_value(next_interruption.capped_last_lap),
            any_value(last_laps.last_lap)
        ) as last_lap
    from starts
    left join next_interruption
        on next_interruption.session_key = starts.session_key
        and next_interruption.neutralisation = starts.neutralisation
        and next_interruption.recorded_at = starts.recorded_at
    left join ends
        on ends.session_key = starts.session_key
        and ends.neutralisation = starts.neutralisation
        and ends.recorded_at > starts.recorded_at
        and ends.recorded_at < coalesce(next_interruption.interrupted_at, timestamp '9999-12-31')
    left join last_laps
        on last_laps.session_key = starts.session_key
    group by starts.session_key, starts.neutralisation, starts.first_lap, starts.recorded_at
),

period_laps as (
    select
        periods.session_key,
        lap_number,
        periods.neutralisation
    from periods
    cross join unnest(generate_array(periods.first_lap, periods.last_lap)) as lap_number
),

red_flag_laps as (
    select session_key, lap_number, 'RED' as neutralisation
    from messages
    where is_red_flag and lap_number is not null
)

select distinct session_key, lap_number, neutralisation from period_laps
union distinct
select session_key, lap_number, neutralisation from red_flag_laps
