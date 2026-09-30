"""Data for the lab site's pitwall section: query the marts, write browser-friendly Parquet.

The site never queries BigQuery itself: `pitwall site-export` writes these files into
`site/src/pitwall/data/` before the site is built (lab ADR 0005).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

QUERIES: dict[str, str] = {
    "races": """
        select
            s.session_key,
            s.meeting_key,
            s.season,
            s.session_name,
            format_date('%Y-%m-%d', date(s.starts_at)) as race_date,
            m.meeting_name,
            m.country_name,
            m.circuit_short_name
        from `{project}.marts.dim_sessions` as s
        inner join `{project}.marts.dim_meetings` as m on m.meeting_key = s.meeting_key
        order by s.starts_at
    """,
    "stints": """
        select
            st.session_key,
            s.season,
            m.circuit_short_name,
            st.driver_number,
            d.name_acronym,
            d.full_name,
            d.team_name,
            d.team_colour_hex,
            st.stint_number,
            st.compound,
            st.first_lap,
            st.last_lap,
            st.laps_in_stint,
            st.tyre_age_at_start,
            st.clean_laps,
            st.degradation_s_per_lap,
            r.finish_position,
            r.grid_position
        from `{project}.marts.fct_stints` as st
        inner join `{project}.marts.dim_sessions` as s on s.session_key = st.session_key
        inner join `{project}.marts.dim_meetings` as m on m.meeting_key = s.meeting_key
        inner join `{project}.marts.dim_session_drivers` as d
            on d.session_key = st.session_key and d.driver_number = st.driver_number
        left join `{project}.marts.fct_session_results` as r
            on r.session_key = st.session_key and r.driver_number = st.driver_number
    """,
    "pit_stops": """
        select
            p.session_key,
            p.driver_number,
            d.name_acronym,
            p.lap_number,
            p.pit_lane_time_s,
            p.stationary_time_s,
            p.source,
            p.compound_before,
            p.compound_after,
            p.position_before,
            p.position_after,
            p.neutralisation
        from `{project}.marts.fct_pit_stops` as p
        inner join `{project}.marts.dim_session_drivers` as d
            on d.session_key = p.session_key and d.driver_number = p.driver_number
    """,
    # Each clean lap compared with its own stint's average: removes car and driver pace, leaving
    # the effect of tyre age (minus the fuel effect, explained on the site).
    "tyre_wear": """
        with clean as (
            select
                l.session_key,
                l.compound,
                l.tyre_age_laps,
                l.lap_time_s - avg(l.lap_time_s) over (
                    partition by l.session_key, l.driver_number, l.stint_number
                ) as delta_s
            from `{project}.marts.fct_laps` as l
            where l.is_clean_lap and l.compound in ('SOFT', 'MEDIUM', 'HARD')
        )

        select
            m.circuit_short_name,
            clean.compound,
            clean.tyre_age_laps,
            round(approx_quantiles(clean.delta_s, 2)[offset(1)], 3) as median_delta_s,
            count(*) as laps
        from clean
        inner join `{project}.marts.dim_sessions` as s on s.session_key = clean.session_key
        inner join `{project}.marts.dim_meetings` as m on m.meeting_key = s.meeting_key
        group by 1, 2, 3
        having count(*) >= 5
    """,
    "undercuts": """
        select
            u.session_key,
            s.season,
            s.session_name,
            m.meeting_name,
            m.circuit_short_name,
            a.name_acronym as attacker,
            a.team_name as attacker_team,
            d.name_acronym as defender,
            d.team_name as defender_team,
            u.attacker_pit_lap,
            u.defender_pit_lap,
            u.is_success,
            u.attacker_pitted_under_neutralisation
        from `{project}.marts.fct_undercut_attempts` as u
        inner join `{project}.marts.dim_sessions` as s on s.session_key = u.session_key
        inner join `{project}.marts.dim_meetings` as m on m.meeting_key = s.meeting_key
        inner join `{project}.marts.dim_session_drivers` as a
            on a.session_key = u.session_key and a.driver_number = u.attacker_driver_number
        inner join `{project}.marts.dim_session_drivers` as d
            on d.session_key = u.session_key and d.driver_number = u.defender_driver_number
    """,
    # Laps run under the Safety Car, Virtual Safety Car or a red flag, for shading race charts.
    "neutralisations": """
        select distinct
            l.session_key,
            l.lap_number,
            l.neutralisation
        from `{project}.marts.fct_laps` as l
        where l.neutralisation is not null
    """,
}


def query(sql: str, *, project: str | None = None, client: Any = None) -> pa.Table:
    """Run `sql` (with `{project}` filled in) and return the result as an Arrow table."""
    project = project or os.environ["PITWALL_BQ_PROJECT"]
    if client is None:
        from google.cloud import bigquery

        client = bigquery.Client(project=project)
    return client.query(sql.format(project=project)).to_arrow()


def browser_friendly(table: pa.Table) -> pa.Table:
    """Narrow 64-bit integers to 32-bit: Arrow JS reads int64 as BigInt, which charts can't plot.

    The cast is safe: a value that doesn't fit raises instead of wrapping around.
    """
    fields = [
        pa.field(field.name, pa.int32()) if pa.types.is_int64(field.type) else field
        for field in table.schema
    ]
    return table.cast(pa.schema(fields))


def export(out_dir: Path, *, project: str | None = None, client: Any = None) -> dict[str, int]:
    """Write one Parquet file per query into `out_dir`; return the rows written per file."""
    project = project or os.environ["PITWALL_BQ_PROJECT"]
    if client is None:
        from google.cloud import bigquery

        client = bigquery.Client(project=project)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, sql in QUERIES.items():
        table = browser_friendly(query(sql, project=project, client=client))
        pq.write_table(table, out_dir / f"{name}.parquet", compression="snappy")
        written[name] = table.num_rows
    return written
