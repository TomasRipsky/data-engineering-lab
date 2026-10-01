from datetime import UTC, datetime

import pytest

from pitwall.contracts import (
    CONTRACTS,
    MEETING_ENDPOINTS,
    REQUIRED_ENDPOINTS,
    SESSION_ENDPOINTS,
    ContractError,
    to_table,
)

NOW = datetime(2025, 4, 1, tzinfo=UTC)
LAP = {"meeting_key": 1255, "session_key": 9998, "driver_number": 81, "lap_number": 1}


def test_required_fields_are_declared_fields():
    for endpoint, contract in CONTRACTS.items():
        assert contract.required <= contract.fields.keys(), endpoint


def test_endpoint_levels():
    assert SESSION_ENDPOINTS[:3] == ("drivers", "laps", "stints")
    assert MEETING_ENDPOINTS == ("starting_grid",)
    assert {"laps", "stints"} == REQUIRED_ENDPOINTS
    assert set(SESSION_ENDPOINTS) | set(MEETING_ENDPOINTS) | {
        "meetings",
        "sessions",
    } == set(CONTRACTS)


def test_casts_to_contract_and_adds_ingested_at():
    record = {
        **LAP,
        "date_start": "2025-03-23T07:03:38.697000+00:00",
        "lap_duration": 98.721,
        "is_pit_out_lap": False,
        "i1_speed": 277,
    }
    table = to_table("laps", [record], NOW)
    assert table.schema == CONTRACTS["laps"].schema
    row = table.to_pylist()[0]
    assert row["date_start"] == datetime(2025, 3, 23, 7, 3, 38, 697000, tzinfo=UTC)
    assert row["duration_sector_1"] is None
    assert row["_ingested_at"] == NOW


def test_mixed_type_field_is_stringified():
    base = {"meeting_key": 1255, "session_key": 9998}
    records = [
        {**base, "driver_number": 81, "gap_to_leader": 0},
        {**base, "driver_number": 4, "gap_to_leader": 11.097},
        {**base, "driver_number": 5, "gap_to_leader": "+1 LAP"},
    ]
    table = to_table("session_result", records, NOW)
    assert table.column("gap_to_leader").to_pylist() == ["0", "11.097", "+1 LAP"]


def test_whole_float_is_accepted_for_int_but_fraction_is_rejected():
    base = {
        "meeting_key": 1255,
        "session_key": 9998,
        "date": "2025-03-23T06:05:20+00:00",
    }
    table = to_table("weather", [{**base, "rainfall": 1.0}], NOW)
    assert table.column("rainfall").to_pylist() == [1]
    with pytest.raises(ContractError, match="weather.rainfall"):
        to_table("weather", [{**base, "rainfall": 0.5}], NOW)


def test_nested_value_in_scalar_field_fails():
    with pytest.raises(ContractError, match="laps.lap_duration"):
        to_table("laps", [{**LAP, "lap_duration": [98.7]}], NOW)


def test_unparseable_timestamp_fails():
    with pytest.raises(ContractError, match="laps.date_start"):
        to_table("laps", [{**LAP, "date_start": "yesterday"}], NOW)


def test_missing_required_field_fails():
    record = {key: value for key, value in LAP.items() if key != "lap_number"}
    with pytest.raises(ContractError, match="required field 'lap_number'"):
        to_table("laps", [record], NOW)


def test_unknown_column_is_dropped_with_warning(caplog):
    table = to_table("laps", [{**LAP, "brand_new_metric": 42}], NOW)
    assert "brand_new_metric" not in table.column_names
    assert "brand_new_metric" in caplog.text


def test_optional_field_absent_from_every_record_warns(caplog):
    record = {**LAP, "lane_time": 20.1, "pit_duration": 23.4, "stop_duration": 2.4}
    to_table("pit", [record], NOW)
    assert "pit: contract fields absent from every record" in caplog.text
    assert "['date', 'lane_duration']" in caplog.text


def test_optional_field_present_in_some_record_does_not_warn(caplog):
    full = {**LAP, "date": "2025-03-23T07:30:00+00:00", "pit_duration": 23.4, "stop_duration": 2.4}
    to_table("pit", [{**full, "lane_duration": 20.1}, full], NOW)
    assert "absent from every record" not in caplog.text


def test_ignored_column_is_dropped_silently(caplog):
    table = to_table("laps", [{**LAP, "segments_sector_1": [2048, 2049]}], NOW)
    assert "segments_sector_1" not in table.column_names
    assert "dropping columns" not in caplog.text


def test_empty_response_gives_empty_table_with_schema(caplog):
    table = to_table("pit", [], NOW)
    assert caplog.text == ""
    assert table.num_rows == 0
    assert table.schema == CONTRACTS["pit"].schema
