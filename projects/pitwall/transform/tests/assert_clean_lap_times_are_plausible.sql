-- Clean F1 race laps take between about 65 s (Austria) and 110 s (Monaco in traffic, Las Vegas).
{{ config(severity='warn') }}

select session_key, driver_number, lap_number, lap_time_s
from {{ ref('fct_laps') }}
where is_clean_lap
    and (lap_time_s < 60 or lap_time_s > 200)
