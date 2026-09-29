"""Ingestion use cases: refresh a season, pick meetings, ingest one meeting atomically."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

log = logging.getLogger(__name__)

SETTLE_TIME = timedelta(hours=6)  # OpenF1 needs some time after a race to publish all data
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

    def finished_meetings(self, now: datetime) -> list[int]:
        """Meetings whose last race session ended at least SETTLE_TIME before `now`."""
        finished = []
        for key in sorted({s["meeting_key"] for s in self.sessions}):
            ends = [s.get("date_end") for s in self.race_sessions(key)]
            settled = (
                ends and all(ends) and max(map(datetime.fromisoformat, ends)) + SETTLE_TIME <= now
            )
            if settled:
                finished.append(key)
        return finished
