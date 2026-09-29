"""Ingestion use cases: refresh a season, pick meetings, ingest one meeting atomically."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pitwall.client import OpenF1Client
from pitwall.contracts import (
    MEETING_ENDPOINTS,
    REQUIRED_ENDPOINTS,
    SESSION_ENDPOINTS,
    to_table,
)
from pitwall.lake import Lake, marker_file, meeting_file, season_file

log = logging.getLogger(__name__)

SETTLE_TIME = timedelta(hours=6)  # OpenF1 needs some time after a race to publish all data
STALE_AFTER = timedelta(days=3)  # still no data after this: fail the run so a human looks
LOOKBACK = timedelta(days=45)  # --latest keeps scanning the previous season this long
Row = dict[str, Any]


@dataclass(frozen=True)
class Season:
    year: int
    meetings: list[Row]
    sessions: list[Row]

    def race_sessions(self, meeting_key: int) -> list[Row]:
        """Race and Sprint sessions of a meeting (both have session_type 'Race'), not cancelled."""
        return [
            s
            for s in self.sessions
            if s["meeting_key"] == meeting_key
            and s["session_type"] == "Race"
            and not s.get("is_cancelled")
        ]

    def race_end(self, meeting_key: int) -> datetime | None:
        """End of the meeting's last race session; None if it has none or an end is unknown."""
        ends = [s.get("date_end") for s in self.race_sessions(meeting_key)]
        if not ends or not all(ends):
            return None
        return max(map(datetime.fromisoformat, ends))

    def finished_meetings(self, now: datetime) -> list[int]:
        """Meetings whose last race session ended at least SETTLE_TIME before `now`."""
        keys = sorted({s["meeting_key"] for s in self.sessions})
        return [
            key
            for key in keys
            if (end := self.race_end(key)) is not None and end + SETTLE_TIME <= now
        ]


def refresh_season(client: OpenF1Client, lake: Lake, year: int, now: datetime) -> Season:
    """Fetch and store the season-level files (meetings, sessions)."""
    meetings = client.get("meetings", year=year)
    sessions = client.get("sessions", year=year)
    lake.write_table(season_file("meetings", year), to_table("meetings", meetings, now))
    lake.write_table(season_file("sessions", year), to_table("sessions", sessions, now))
    return Season(year, meetings, sessions)


def ingest_meeting(
    client: OpenF1Client, lake: Lake, season: Season, meeting_key: int, now: datetime
) -> bool:
    """Fetch, validate and write one meeting. Returns False when it was skipped.

    Everything is fetched and validated in memory first; the old marker is removed before
    the first write and the new one written last, so a crash never exposes mixed files.
    """
    races = season.race_sessions(meeting_key)
    if not races:
        log.warning("meeting %s: no race sessions; skipped", meeting_key)
        return False

    first_request = client.request_count
    rows: dict[str, list[Row]] = {e: [] for e in (*SESSION_ENDPOINTS, *MEETING_ENDPOINTS)}
    for race in races:
        for endpoint in SESSION_ENDPOINTS:
            fetched = client.get(endpoint, session_key=race["session_key"])
            if endpoint in REQUIRED_ENDPOINTS and not fetched:
                log.warning(
                    "meeting %s: no %s yet for session %s; skipped, will retry next run",
                    meeting_key,
                    endpoint,
                    race["session_key"],
                )
                return False
            rows[endpoint] += fetched
    for endpoint in MEETING_ENDPOINTS:
        rows[endpoint] = client.get(endpoint, meeting_key=meeting_key)
    tables = {endpoint: to_table(endpoint, records, now) for endpoint, records in rows.items()}

    marker = marker_file(season.year, meeting_key)
    lake.delete(marker)
    for endpoint, table in tables.items():
        lake.write_table(meeting_file(endpoint, season.year, meeting_key), table)
    lake.write_json(
        marker,
        {
            "meeting_key": meeting_key,
            "season": season.year,
            "session_keys": sorted(race["session_key"] for race in races),
            "rows": {endpoint: table.num_rows for endpoint, table in tables.items()},
            "requests": client.request_count - first_request,
            "ingested_at": now.isoformat(),
        },
    )
    log.info("meeting %s: ingested %d laps", meeting_key, tables["laps"].num_rows)
    return True


def ingest_latest(client: OpenF1Client, lake: Lake, now: datetime) -> list[int]:
    """Scheduled mode: finished meetings not yet in the lake.

    Also scans the previous season for LOOKBACK days, so a late-December race is not lost at
    New Year. A meeting still without data STALE_AFTER its race fails the run (after the
    others are ingested) instead of being skipped silently forever.
    """
    done = lake.markers()
    ingested, stale = [], []
    for year in sorted({(now - LOOKBACK).year, now.year}):
        season = refresh_season(client, lake, year, now)
        for key in season.finished_meetings(now):
            if key in done:
                continue
            if ingest_meeting(client, lake, season, key, now):
                ingested.append(key)
            elif season.race_end(key) + STALE_AFTER <= now:
                stale.append(key)
    if stale:
        raise RuntimeError(
            f"meetings {stale} still have no laps/stints {STALE_AFTER} after the race "
            f"(ingested this run: {ingested}); check OpenF1"
        )
    return ingested


def ingest_season(client: OpenF1Client, lake: Lake, year: int, now: datetime) -> list[int]:
    """Backfill: (re)ingest every finished meeting of a season."""
    season = refresh_season(client, lake, year, now)
    finished = season.finished_meetings(now)
    return [key for key in finished if ingest_meeting(client, lake, season, key, now)]


def ingest_one(client: OpenF1Client, lake: Lake, meeting_key: int, now: datetime) -> list[int]:
    """(Re)ingest a single meeting, e.g. after a data correction upstream."""
    found = client.get("meetings", meeting_key=meeting_key)
    if not found:
        raise ValueError(f"meeting {meeting_key} not found in OpenF1")
    season = refresh_season(client, lake, found[0]["year"], now)
    if meeting_key not in season.finished_meetings(now):
        log.warning("meeting %s has not finished (or has no race); skipped", meeting_key)
        return []
    return [meeting_key] if ingest_meeting(client, lake, season, meeting_key, now) else []
