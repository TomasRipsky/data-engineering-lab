-- grain: one row per driver per Race or Sprint session
with results as (
    select * from {{ ref('stg_openf1__session_result') }}
),

grid as (
    select * from {{ ref('stg_openf1__starting_grid') }}
),

sessions as (
    select * from {{ ref('stg_openf1__sessions') }}
),

grid_by_race as (
    -- OpenF1 attaches each grid to the qualifying session that produced it
    select
        race.session_key,
        grid.driver_number,
        grid.grid_position
    from grid
    inner join sessions as quali
        on quali.session_key = grid.qualifying_session_key
    inner join sessions as race
        on race.meeting_key = quali.meeting_key
        and race.session_type = 'Race'
        and race.session_name = case quali.session_name
            when 'Qualifying' then 'Race'
            when 'Sprint Qualifying' then 'Sprint'
            when 'Sprint Shootout' then 'Sprint'
        end
)

select
    results.session_key,
    results.meeting_key,
    results.driver_number,
    grid_by_race.grid_position,
    results.finish_position,
    grid_by_race.grid_position - results.finish_position as positions_gained,
    results.points,
    results.laps_completed,
    results.did_not_finish,
    results.did_not_start,
    results.disqualified,
    results.gap_to_leader
from results
left join grid_by_race
    on grid_by_race.session_key = results.session_key
    and grid_by_race.driver_number = results.driver_number
