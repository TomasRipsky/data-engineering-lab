-- grain: one row per race weekend with at least one analysed race
with meetings as (
    select * from {{ ref('stg_openf1__meetings') }}
),

analysed as (
    select distinct meeting_key from {{ ref('dim_sessions') }}
)

select
    meetings.meeting_key,
    meetings.meeting_name,
    meetings.meeting_official_name,
    meetings.season,
    meetings.country_name,
    meetings.location,
    meetings.circuit_short_name,
    meetings.circuit_type,
    meetings.starts_at,
    meetings.ends_at
from meetings
inner join analysed
    on analysed.meeting_key = meetings.meeting_key
