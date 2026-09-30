from datetime import UTC, datetime

import pytest

from pitwall.ingest import ingest_one
from pitwall.lake import Lake, marker_file
from pitwall.load import RAW_DATASET, bigquery_loader, load, load_plan

NOW = datetime(2025, 4, 1, tzinfo=UTC)


@pytest.fixture
def lake(tmp_path):
    return Lake(str(tmp_path / "lake"))


def test_plan_covers_every_endpoint_from_marked_meetings_only(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    plan = load_plan(lake)
    assert set(plan) == {
        "openf1_meetings",
        "openf1_sessions",
        "openf1_drivers",
        "openf1_laps",
        "openf1_stints",
        "openf1_pit",
        "openf1_position",
        "openf1_weather",
        "openf1_race_control",
        "openf1_session_result",
        "openf1_overtakes",
        "openf1_starting_grid",
    }
    assert plan["openf1_laps"] == [
        lake.uri_of("raw/laps/season=2025/meeting_key=1255/part.parquet")
    ]
    assert plan["openf1_sessions"] == [lake.uri_of("raw/sessions/season=2025/part.parquet")]


def test_plan_ignores_unmarked_meetings(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    lake.delete(marker_file(2025, 1255))  # e.g. a crashed re-ingestion
    assert all(uris == [] for uris in load_plan(lake).values())


def test_plan_only_uses_endpoints_listed_in_each_manifest(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    manifest = lake.read_json(marker_file(2025, 1255))
    del manifest["rows"]["overtakes"]  # a meeting ingested before overtakes existed
    lake.write_json(marker_file(2025, 1255), manifest)
    assert load_plan(lake)["openf1_overtakes"] == []


def test_load_calls_the_loader_per_table_with_uris(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    calls = {}

    def fake_loader(table, uris):
        calls[table] = uris
        return len(uris)

    result = load(lake, fake_loader)
    assert result["openf1_laps"] == 1
    assert set(calls) == set(result)


def test_load_refuses_an_empty_lake(lake):
    with pytest.raises(ValueError, match="no complete meetings"):
        load(lake, lambda table, uris: 0)


def test_bigquery_loader_truncates_and_loads_parquet():
    class Job:
        output_rows = 42

        def result(self):
            return self

    class FakeClient:
        def load_table_from_uri(self, uris, destination, job_config):
            self.call = (uris, destination, job_config)
            return Job()

    client = FakeClient()
    loader = bigquery_loader("pitwall-tr-dev", client=client)
    assert loader("openf1_laps", ["gs://b/raw/laps/x.parquet"]) == 42
    uris, destination, config = client.call
    assert destination == f"pitwall-tr-dev.{RAW_DATASET}.openf1_laps"
    assert config.source_format == "PARQUET"
    assert config.write_disposition == "WRITE_TRUNCATE"
