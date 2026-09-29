"""Explicit schemas for OpenF1 endpoints: the contract between the API and the lake.

A required field that is missing fails the run; an unknown field is dropped with a warning
until it is added here by PR, so schema evolution is always a reviewed decision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pyarrow as pa

log = logging.getLogger(__name__)

INT = pa.int64()
FLOAT = pa.float64()
STR = pa.string()
BOOL = pa.bool_()
TS = pa.timestamp("us", tz="UTC")
KEYS = {"meeting_key": INT, "session_key": INT}


class ContractError(ValueError):
    """The API returned data that breaks an endpoint contract."""


@dataclass(frozen=True)
class Contract:
    level: str  # "season", "meeting" or "session": which key the endpoint is fetched by
    fields: dict[str, pa.DataType]
    required: frozenset[str]
    ignored: frozenset[str] = frozenset()

    @property
    def schema(self) -> pa.Schema:
        return pa.schema([*self.fields.items(), ("_ingested_at", TS)])


def _contract(level, fields, required, ignored=()) -> Contract:
    return Contract(level, fields, frozenset(required), frozenset(ignored))


# Order matters: session endpoints are fetched in this order, required ones first.
CONTRACTS: dict[str, Contract] = {
    "meetings": _contract(
        "season",
        {
            "meeting_key": INT,
            "meeting_name": STR,
            "meeting_official_name": STR,
            "location": STR,
            "country_key": INT,
            "country_code": STR,
            "country_name": STR,
            "circuit_key": INT,
            "circuit_short_name": STR,
            "circuit_type": STR,
            "gmt_offset": STR,
            "date_start": TS,
            "date_end": TS,
            "year": INT,
            "is_cancelled": BOOL,
        },
        required={"meeting_key", "year"},
        ignored={"country_flag", "circuit_info_url", "circuit_image"},
    ),
    "sessions": _contract(
        "season",
        {
            "session_key": INT,
            "meeting_key": INT,
            "session_type": STR,
            "session_name": STR,
            "date_start": TS,
            "date_end": TS,
            "circuit_key": INT,
            "circuit_short_name": STR,
            "country_key": INT,
            "country_code": STR,
            "country_name": STR,
            "location": STR,
            "gmt_offset": STR,
            "year": INT,
            "is_cancelled": BOOL,
        },
        required={"session_key", "meeting_key", "session_type", "year"},
    ),
    "drivers": _contract(
        "session",
        {
            **KEYS,
            "driver_number": INT,
            "broadcast_name": STR,
            "full_name": STR,
            "name_acronym": STR,
            "team_name": STR,
            "team_colour": STR,
            "first_name": STR,
            "last_name": STR,
            "country_code": STR,
        },
        required={*KEYS, "driver_number"},
        ignored={"headshot_url"},
    ),
    "laps": _contract(
        "session",
        {
            **KEYS,
            "driver_number": INT,
            "lap_number": INT,
            "date_start": TS,
            "lap_duration": FLOAT,
            "duration_sector_1": FLOAT,
            "duration_sector_2": FLOAT,
            "duration_sector_3": FLOAT,
            "i1_speed": INT,
            "i2_speed": INT,
            "st_speed": INT,
            "is_pit_out_lap": BOOL,
        },
        required={*KEYS, "driver_number", "lap_number"},
        ignored={"segments_sector_1", "segments_sector_2", "segments_sector_3"},
    ),
    "stints": _contract(
        "session",
        {
            **KEYS,
            "driver_number": INT,
            "stint_number": INT,
            "lap_start": INT,
            "lap_end": INT,
            "compound": STR,
            "tyre_age_at_start": INT,
        },
        required={*KEYS, "driver_number", "stint_number"},
    ),
    "pit": _contract(
        "session",
        {
            **KEYS,
            "driver_number": INT,
            "lap_number": INT,
            "date": TS,
            "pit_duration": FLOAT,
            "lane_duration": FLOAT,
            "stop_duration": FLOAT,
        },
        required={*KEYS, "driver_number", "lap_number"},
    ),
    "position": _contract(
        "session",
        {**KEYS, "driver_number": INT, "date": TS, "position": INT},
        required={*KEYS, "driver_number", "date"},
    ),
    "weather": _contract(
        "session",
        {
            **KEYS,
            "date": TS,
            "air_temperature": FLOAT,
            "track_temperature": FLOAT,
            "humidity": FLOAT,
            "pressure": FLOAT,
            "rainfall": INT,
            "wind_direction": INT,
            "wind_speed": FLOAT,
        },
        required={*KEYS, "date"},
    ),
    "race_control": _contract(
        "session",
        {
            **KEYS,
            "date": TS,
            "lap_number": INT,
            "driver_number": INT,
            "category": STR,
            "flag": STR,
            "scope": STR,
            "sector": INT,
            "qualifying_phase": INT,
            "message": STR,
        },
        required={*KEYS, "date"},
    ),
    "session_result": _contract(
        "session",
        {
            **KEYS,
            "driver_number": INT,
            "position": INT,
            "number_of_laps": INT,
            "points": FLOAT,
            "dnf": BOOL,
            "dns": BOOL,
            "dsq": BOOL,
            "duration": FLOAT,
            "gap_to_leader": STR,  # 0, 11.097 or "+1 LAP": stored as text
        },
        required={*KEYS, "driver_number"},
    ),
    "overtakes": _contract(
        "session",
        {
            **KEYS,
            "date": TS,
            "overtaking_driver_number": INT,
            "overtaken_driver_number": INT,
            "position": INT,
        },
        required={*KEYS, "date", "overtaking_driver_number", "overtaken_driver_number"},
    ),
    "starting_grid": _contract(
        "meeting",  # attached to qualifying sessions, so fetched by meeting_key
        {**KEYS, "driver_number": INT, "position": INT, "lap_duration": FLOAT},
        required={*KEYS, "driver_number"},
    ),
}

SESSION_ENDPOINTS = tuple(name for name, c in CONTRACTS.items() if c.level == "session")
MEETING_ENDPOINTS = tuple(name for name, c in CONTRACTS.items() if c.level == "meeting")
REQUIRED_ENDPOINTS = frozenset({"laps", "stints"})


def _coerce(endpoint: str, name: str, value: Any, dtype: pa.DataType) -> Any:
    if value is None:
        return None
    try:
        if isinstance(value, list | dict):
            raise TypeError("nested value in a scalar field")
        if dtype == TS:
            return datetime.fromisoformat(value)
        if dtype == STR:
            return str(value)
        if dtype == FLOAT:
            return float(value)
        if dtype == BOOL:
            if not isinstance(value, bool):
                raise TypeError("not a boolean")
            return value
        if dtype == INT:
            if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
                raise TypeError("not an integer")
            return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{endpoint}.{name}: cannot cast {value!r} to {dtype}") from exc
    raise AssertionError(f"unsupported contract type {dtype}")


def to_table(endpoint: str, records: list[dict[str, Any]], ingested_at: datetime) -> pa.Table:
    """Cast API records to the endpoint contract and stamp them with `_ingested_at`."""
    contract = CONTRACTS[endpoint]
    unknown = {key for record in records for key in record} - contract.fields.keys()
    unknown -= contract.ignored
    if unknown:
        log.warning("%s: dropping columns not in the contract: %s", endpoint, sorted(unknown))

    columns = {}
    for name, dtype in contract.fields.items():
        values = [_coerce(endpoint, name, record.get(name), dtype) for record in records]
        if name in contract.required and any(value is None for value in values):
            raise ContractError(f"{endpoint}: required field {name!r} is missing or null")
        columns[name] = pa.array(values, type=dtype)
    columns["_ingested_at"] = pa.array([ingested_at] * len(records), type=TS)
    return pa.table(columns, schema=contract.schema)
