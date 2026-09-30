-- grain: one row per lap of one driver in one session
with laps as (
    select * from {{ ref('stg_openf1__laps') }}
),

stints as (
    select * from {{ ref('stg_openf1__stints') }}
),

pits as (
    select session_key, driver_number, lap_number from {{ ref('stg_openf1__pit') }}
),

positions as (
    select session_key, driver_number, recorded_at, position
    from {{ ref('stg_openf1__position') }}
),

neutralised as (
    -- a lap can see several: a red flag outranks the SC, which outranks the VSC
    select
        session_key,
        lap_number,
        case
            when countif(neutralisation = 'RED') > 0 then 'RED'
            when countif(neutralisation = 'SC') > 0 then 'SC'
            else 'VSC'
        end as neutralisation
    from {{ ref('int_neutralised_laps') }}
    group by session_key, lap_number
),

timed as (
    select
        laps.*,
        coalesce(
            timestamp_add(
                laps.started_at, interval cast(round(laps.lap_time_s * 1000) as int64) millisecond
            ),
            lead(laps.started_at) over (
                partition by laps.session_key, laps.driver_number order by laps.lap_number
            )
        ) as ended_at
    from laps
),

lap_positions as (
    select
        timed.session_key,
        timed.driver_number,
        timed.lap_number,
        positions.position
    from timed
    inner join positions
        on positions.session_key = timed.session_key
        and positions.driver_number = timed.driver_number
        and positions.recorded_at <= timed.ended_at
    where true
    qualify row_number() over (
        partition by timed.session_key, timed.driver_number, timed.lap_number
        order by positions.recorded_at desc
    ) = 1
),

enriched as (
    select
        timed.session_key,
        timed.meeting_key,
        timed.driver_number,
        timed.lap_number,
        timed.started_at,
        timed.ended_at,
        timed.lap_time_s,
        timed.sector_1_s,
        timed.sector_2_s,
        timed.sector_3_s,
        timed.speed_trap_kph,
        stints.stint_number,
        stints.compound,
        stints.tyre_age_at_start + (timed.lap_number - stints.first_lap) as tyre_age_laps,
        pits.lap_number is not null as is_pit_in_lap,
        timed.is_pit_out_lap,
        neutralised.neutralisation,
        lap_positions.position as position_end_of_lap,
        percentile_cont(timed.lap_time_s, 0.5) over (
            partition by timed.session_key
        ) as session_median_lap_time_s
    from timed
    left join stints
        on stints.session_key = timed.session_key
        and stints.driver_number = timed.driver_number
        and timed.lap_number between stints.first_lap and stints.last_lap
    left join pits
        on pits.session_key = timed.session_key
        and pits.driver_number = timed.driver_number
        and pits.lap_number = timed.lap_number
    left join neutralised
        on neutralised.session_key = timed.session_key
        and neutralised.lap_number = timed.lap_number
    left join lap_positions
        on lap_positions.session_key = timed.session_key
        and lap_positions.driver_number = timed.driver_number
        and lap_positions.lap_number = timed.lap_number
    where true
    -- overlapping stints in the source must not duplicate a lap: keep the later stint
    qualify row_number() over (
        partition by timed.session_key, timed.driver_number, timed.lap_number
        order by stints.stint_number desc
    ) = 1
)

select
    *,
    (
        lap_number > 1
        and lap_time_s is not null
        and not is_pit_in_lap
        and not is_pit_out_lap
        and neutralisation is null
        and lap_time_s <= 1.2 * session_median_lap_time_s
    ) as is_clean_lap
from enriched
