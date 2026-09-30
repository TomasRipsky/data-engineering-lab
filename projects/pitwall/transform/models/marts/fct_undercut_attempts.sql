-- grain: one row per pit stop that is an undercut attempt
with laps as (
    select session_key, driver_number, lap_number, position_end_of_lap
    from {{ ref('int_laps_enriched') }}
),

pits as (
    select session_key, driver_number, lap_number, is_under_neutralisation
    from {{ ref('fct_pit_stops') }}
),

attacker_stops as (
    select
        pits.session_key,
        pits.driver_number as attacker_driver_number,
        pits.lap_number as attacker_pit_lap,
        pits.is_under_neutralisation as attacker_pitted_under_neutralisation,
        lap_before.position_end_of_lap as attacker_position_before
    from pits
    inner join laps as lap_before
        on lap_before.session_key = pits.session_key
        and lap_before.driver_number = pits.driver_number
        and lap_before.lap_number = pits.lap_number - 1
),

car_ahead as (
    select
        attacker_stops.*,
        ahead.driver_number as defender_driver_number
    from attacker_stops
    inner join laps as ahead
        on ahead.session_key = attacker_stops.session_key
        and ahead.lap_number = attacker_stops.attacker_pit_lap - 1
        and ahead.position_end_of_lap = attacker_stops.attacker_position_before - 1
),

attempts as (
    select
        car_ahead.session_key,
        car_ahead.attacker_driver_number,
        car_ahead.defender_driver_number,
        car_ahead.attacker_pit_lap,
        car_ahead.attacker_position_before,
        car_ahead.attacker_pitted_under_neutralisation,
        min(response.lap_number) as defender_pit_lap
    from car_ahead
    inner join pits as response
        on response.session_key = car_ahead.session_key
        and response.driver_number = car_ahead.defender_driver_number
        and response.lap_number between car_ahead.attacker_pit_lap + 1
            and car_ahead.attacker_pit_lap + 3
    group by 1, 2, 3, 4, 5, 6
)

select
    attempts.session_key,
    attempts.attacker_driver_number,
    attempts.defender_driver_number,
    attempts.attacker_pit_lap,
    attempts.defender_pit_lap,
    attempts.defender_pit_lap + 1 as comparison_lap,
    attempts.attacker_position_before,
    attacker_after.position_end_of_lap as attacker_position_after,
    defender_after.position_end_of_lap as defender_position_after,
    attacker_after.position_end_of_lap < defender_after.position_end_of_lap as is_success,
    attempts.attacker_pitted_under_neutralisation
from attempts
left join laps as attacker_after
    on attacker_after.session_key = attempts.session_key
    and attacker_after.driver_number = attempts.attacker_driver_number
    and attacker_after.lap_number = attempts.defender_pit_lap + 1
left join laps as defender_after
    on defender_after.session_key = attempts.session_key
    and defender_after.driver_number = attempts.defender_driver_number
    and defender_after.lap_number = attempts.defender_pit_lap + 1
