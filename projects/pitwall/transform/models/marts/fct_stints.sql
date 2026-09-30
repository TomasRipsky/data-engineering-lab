-- grain: one row per stint (one driver on one set of tyres in one session)
with stints as (
    select * from {{ ref('stg_openf1__stints') }}
),

clean_laps as (
    select
        session_key,
        driver_number,
        stint_number,
        count(*) as clean_laps,
        avg(lap_time_s) as mean_clean_lap_time_s,
        -- least-squares slope of lap time against tyre age
        covar_samp(lap_time_s, tyre_age_laps) / nullif(var_samp(tyre_age_laps), 0) as slope
    from {{ ref('int_laps_enriched') }}
    where is_clean_lap
    group by session_key, driver_number, stint_number
)

select
    stints.session_key,
    stints.meeting_key,
    stints.driver_number,
    stints.stint_number,
    stints.compound,
    stints.first_lap,
    stints.last_lap,
    stints.last_lap - stints.first_lap + 1 as laps_in_stint,
    stints.tyre_age_at_start,
    coalesce(clean_laps.clean_laps, 0) as clean_laps,
    round(clean_laps.mean_clean_lap_time_s, 3) as mean_clean_lap_time_s,
    if(clean_laps.clean_laps >= 5, round(clean_laps.slope, 4), null) as degradation_s_per_lap
from stints
left join clean_laps
    on clean_laps.session_key = stints.session_key
    and clean_laps.driver_number = stints.driver_number
    and clean_laps.stint_number = stints.stint_number
where stints.has_valid_lap_range -- invalid ranges stay in staging and in the audit warning
