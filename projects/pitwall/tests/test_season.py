from datetime import UTC, datetime

from pitwall.ingest import Season

NOW = datetime(2025, 3, 24, 6, 0, tzinfo=UTC)


def session(meeting_key, session_key, *, kind="Race", end="2025-03-23T09:00:00+00:00", **extra):
    return {
        "meeting_key": meeting_key,
        "session_key": session_key,
        "session_type": kind,
        "date_end": end,
        "is_cancelled": False,
        **extra,
    }


def test_race_sessions_keep_race_and_sprint_but_not_cancelled_or_other_types():
    season = Season(
        2025,
        [],
        [
            session(1, 10, session_name="Sprint"),
            session(1, 11, session_name="Race"),
            session(1, 12, kind="Qualifying"),
            session(1, 13, is_cancelled=True),
            session(2, 20),
        ],
    )
    assert [s["session_key"] for s in season.race_sessions(1)] == [10, 11]


def test_finished_meetings_wait_for_the_last_race_session_to_settle():
    season = Season(
        2025,
        [],
        [
            session(1, 10),  # ended 21 h before NOW: finished
            session(2, 20, kind="Practice", end="2025-03-01T16:00:00+00:00"),  # testing: no race
            session(3, 30, end="2025-03-24T01:00:00+00:00"),  # ended 5 h before NOW
            session(4, 40, end=None),  # end unknown
            session(5, 50, end="2025-03-22T09:00:00+00:00"),  # sprint long done...
            session(5, 51, end="2025-03-24T05:00:00+00:00"),  # ...but the race is not settled
            session(6, 60, end="2025-03-23T09:00:00+00:00", is_cancelled=True),  # cancelled
        ],
    )
    assert season.finished_meetings(NOW) == [1]


def test_settle_time_boundary_is_inclusive():
    season = Season(2025, [], [session(1, 10, end="2025-03-24T00:00:00+00:00")])
    assert season.finished_meetings(NOW) == [1]
