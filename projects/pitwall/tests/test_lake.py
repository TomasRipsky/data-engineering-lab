import pyarrow as pa
import pytest

from pitwall.lake import Lake, marker_file, meeting_file, season_file


@pytest.fixture
def lake(tmp_path):
    return Lake(str(tmp_path / "lake with spaces"))


def test_path_conventions():
    assert season_file("sessions", 2025) == "raw/sessions/season=2025/part.parquet"
    assert meeting_file("laps", 2025, 1255) == "raw/laps/season=2025/meeting_key=1255/part.parquet"
    assert marker_file(2025, 1255) == "raw/_success/season=2025/meeting_key=1255.json"


def test_table_roundtrip_does_not_add_partition_columns(lake):
    table = pa.table({"lap_number": [1, 2]})
    lake.write_table(meeting_file("laps", 2025, 1255), table)
    assert lake.read_table(meeting_file("laps", 2025, 1255)).equals(table)


def test_plain_path_and_file_uri_with_spaces_are_the_same_lake(tmp_path):
    root = tmp_path / "Data Engineering" / "lake"
    Lake(str(root)).write_json("raw/_success/season=2025/meeting_key=1.json", {"ok": True})
    assert Lake(root.as_uri()).read_json("raw/_success/season=2025/meeting_key=1.json") == {
        "ok": True
    }


def test_exists_and_delete(lake):
    rel = marker_file(2025, 1255)
    assert not lake.exists(rel)
    lake.write_json(rel, {"meeting_key": 1255})
    assert lake.exists(rel)
    lake.delete(rel)
    assert not lake.exists(rel)
    lake.delete(rel)  # deleting something absent is not an error


def test_markers_lists_meeting_keys_across_seasons(lake):
    assert lake.markers() == set()
    lake.write_json(marker_file(2024, 1229), {})
    lake.write_json(marker_file(2025, 1255), {})
    lake.write_table(meeting_file("laps", 2025, 1256), pa.table({"a": [1]}))  # no marker
    assert lake.markers() == {1229, 1255}


def test_object_store_writes_never_create_directories(monkeypatch):
    # On GCS, pyarrow's create_dir on a missing bucket would create the bucket.
    lake = Lake("gs://some-bucket")
    written = {}

    class NoDirs:
        def create_dir(self, path, recursive=False):
            raise AssertionError(f"create_dir called for {path}")

        def open_output_stream(self, path):
            import io

            class Sink(io.BytesIO):
                def close(self):
                    written[path] = self.getvalue()
                    super().close()

            return Sink()

    monkeypatch.setattr(lake, "_fs", NoDirs())
    lake.write_json(marker_file(2025, 1255), {"meeting_key": 1255})
    assert list(written) == ["some-bucket/raw/_success/season=2025/meeting_key=1255.json"]


def test_uri_of_points_at_the_object(tmp_path):
    assert Lake("gs://pitwall-tr-dev-raw").uri_of("raw/laps/x.parquet") == (
        "gs://pitwall-tr-dev-raw/raw/laps/x.parquet"
    )
    local = Lake(str(tmp_path / "lake"))
    assert local.is_local
    assert local.uri_of("raw/a.parquet") == f"{tmp_path / 'lake'}/raw/a.parquet"


def test_manifests_returns_every_marker(lake):
    lake.write_json(marker_file(2024, 1229), {"meeting_key": 1229, "season": 2024})
    lake.write_json(marker_file(2025, 1255), {"meeting_key": 1255, "season": 2025})
    keys = sorted(m["meeting_key"] for m in lake.manifests())
    assert keys == [1229, 1255]
