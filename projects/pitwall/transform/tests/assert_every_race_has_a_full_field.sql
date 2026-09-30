-- A race has 20 cars (22 from 2026). Fewer than 18 drivers with laps means missing data.
{{ config(severity='warn') }}

select
    session_key,
    count(distinct driver_number) as drivers_with_laps
from {{ ref('stg_openf1__laps') }}
group by session_key
having count(distinct driver_number) < 18
