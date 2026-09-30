import re

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pitwall.site_data import QUERIES, browser_friendly, export, query


class FakeClient:
    def __init__(self, table):
        self.table = table
        self.sql = []

    def query(self, sql):
        self.sql.append(sql)
        return self

    def to_arrow(self):
        return self.table


def test_query_fills_in_the_project():
    client = FakeClient(pa.table({"a": [1]}))
    query(
        "select 1 from `{project}.marts.dim_sessions`",
        project="pitwall-tr-dev",
        client=client,
    )
    assert client.sql == ["select 1 from `pitwall-tr-dev.marts.dim_sessions`"]


def test_browser_friendly_narrows_64_bit_integers():
    table = pa.table(
        {"lap": pa.array([1, 57], pa.int64()), "time": [90.1, 91.2], "name": ["A", "B"]}
    )
    friendly = browser_friendly(table)
    assert friendly.schema.field("lap").type == pa.int32()
    assert friendly.schema.field("time").type == pa.float64()
    assert friendly.column("lap").to_pylist() == [1, 57]


def test_browser_friendly_refuses_to_truncate():
    with pytest.raises(pa.ArrowInvalid):
        browser_friendly(pa.table({"big": pa.array([2**40], pa.int64())}))


def test_export_writes_one_browser_friendly_file_per_query(tmp_path):
    client = FakeClient(pa.table({"n": pa.array([7], pa.int64())}))
    rows = export(tmp_path / "data", project="p", client=client)
    assert rows == {name: 1 for name in QUERIES}
    for name in QUERIES:
        table = pq.read_table(tmp_path / "data" / f"{name}.parquet")
        assert table.schema.field("n").type == pa.int32()
    assert all("`p.marts." in sql for sql in client.sql)


def test_queries_only_read_marts():
    assert set(QUERIES) == {"races", "stints", "pit_stops", "tyre_wear", "undercuts"}
    for name, sql in QUERIES.items():
        tables = re.findall(r"`([^`]+)`", sql)
        assert tables and all(t.startswith("{project}.marts.") for t in tables), name
        assert not re.search(r"\b(insert|update|delete|merge|create|drop)\b", sql, re.I), name
