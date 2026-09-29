from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pitwall.client import NO_RESULTS
from pitwall.contracts import MEETING_ENDPOINTS, SESSION_ENDPOINTS
from pitwall.ingest import ingest_latest, ingest_one, ingest_season
from pitwall.lake import Lake, marker_file, meeting_file, season_file

NOW = datetime(2025, 4, 1, tzinfo=UTC)
ENDPOINTS = [*SESSION_ENDPOINTS, *MEETING_ENDPOINTS]


@pytest.fixture
def lake(tmp_path):
    return Lake(str(tmp_path / "lake"))


def meeting_tables(lake):
    return {
        endpoint: lake.read_table(meeting_file(endpoint, 2025, 1255)).drop_columns(["_ingested_at"])
        for endpoint in ENDPOINTS
    }


def test_ingest_one_writes_every_endpoint_and_a_manifest(fixture_client, lake):
    assert ingest_one(fixture_client, lake, 1255, NOW) == [1255]

    assert lake.exists(season_file("meetings", 2025))
    assert lake.exists(season_file("sessions", 2025))
    for endpoint in ENDPOINTS:
        assert lake.exists(meeting_file(endpoint, 2025, 1255)), endpoint

    manifest = lake.read_json(marker_file(2025, 1255))
    assert manifest["session_keys"] == [9993, 9998]
    laps = lake.read_table(meeting_file("laps", 2025, 1255))
    assert manifest["rows"]["laps"] == laps.num_rows > 0
    assert set(laps.column("session_key").to_pylist()) == {9993, 9998}
    assert set(laps.column("driver_number").to_pylist()) == {4, 81}


def test_reingesting_a_meeting_is_idempotent(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    first = meeting_tables(lake)
    ingest_one(fixture_client, lake, 1255, NOW + timedelta(days=1))
    second = meeting_tables(lake)
    for endpoint in ENDPOINTS:
        assert second[endpoint].equals(first[endpoint]), endpoint


def test_latest_skips_meetings_already_in_the_lake(fixture_client, lake):
    assert ingest_latest(fixture_client, lake, NOW) == [1255]
    before = fixture_client.request_count
    assert ingest_latest(fixture_client, lake, NOW) == []
    assert fixture_client.request_count - before == 2  # only the season refresh


def test_season_backfill_reingests_marked_meetings(fixture_client, lake):
    ingest_latest(fixture_client, lake, NOW)
    assert ingest_season(fixture_client, lake, 2025, NOW) == [1255]


def test_unfinished_meeting_is_not_ingested(fixture_client, lake):
    during_the_race = datetime(2025, 3, 23, 8, 0, tzinfo=UTC)
    assert ingest_one(fixture_client, lake, 1255, during_the_race) == []
    assert lake.markers() == set()


def test_crash_while_rewriting_leaves_the_meeting_unmarked(fixture_client, lake, monkeypatch):
    ingest_one(fixture_client, lake, 1255, NOW)
    real_write = lake.write_table

    def failing_write(rel, table):
        if "meeting_key=" in rel:
            raise OSError("disk gone")
        real_write(rel, table)

    monkeypatch.setattr(lake, "write_table", failing_write)
    with pytest.raises(OSError):
        ingest_one(fixture_client, lake, 1255, NOW)
    assert lake.markers() == set()  # next --latest run will retry it


def test_missing_required_data_skips_the_meeting_without_writing(
    make_client, openf1_fixtures, lake, caplog
):
    def no_laps(request):
        if request.url.path.endswith("/laps"):
            return httpx.Response(404, json=NO_RESULTS)
        return openf1_fixtures(request)

    assert ingest_one(make_client(no_laps), lake, 1255, NOW) == []
    assert lake.markers() == set()
    assert not lake.exists(meeting_file("drivers", 2025, 1255))
    assert "no laps yet" in caplog.text


def test_unknown_meeting_is_an_error(fixture_client, lake):
    with pytest.raises(ValueError, match="99999"):
        ingest_one(fixture_client, lake, 99999, NOW)


def test_latest_still_covers_the_previous_season_in_january(fixture_client, lake):
    # A late-season GP not yet ingested must not be forgotten when the year changes.
    january = datetime(2026, 1, 10, tzinfo=UTC)
    assert ingest_latest(fixture_client, lake, january) == [1255]


def test_latest_fails_loudly_when_a_meeting_stays_without_data(make_client, openf1_fixtures, lake):
    def no_laps(request):
        if request.url.path.endswith("/laps"):
            return httpx.Response(404, json=NO_RESULTS)
        return openf1_fixtures(request)

    client = make_client(no_laps)
    two_days_after = datetime(2025, 3, 25, 12, 0, tzinfo=UTC)
    assert ingest_latest(client, lake, two_days_after) == []  # may still arrive: just wait
    with pytest.raises(RuntimeError, match="1255"):
        ingest_latest(client, lake, NOW)  # 9 days after the race: someone must look
