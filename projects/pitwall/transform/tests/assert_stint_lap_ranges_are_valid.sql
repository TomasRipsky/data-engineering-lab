-- A stint needs both ends and must end on or after the lap it starts. OpenF1 has a handful of
-- missing or inverted ranges (10 in 2025); they are reported (warn) and kept out of the marts.
{{ config(severity='warn') }}

select session_key, driver_number, stint_number, first_lap, last_lap
from {{ ref('stg_openf1__stints') }}
where not has_valid_lap_range
