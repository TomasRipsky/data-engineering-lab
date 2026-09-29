from datetime import UTC, datetime

import pytest

from pitwall.cli import main
from pitwall.lake import Lake


@pytest.fixture
def lake_env(monkeypatch, tmp_path):
    uri = str(tmp_path / "lake")
    monkeypatch.setenv("PITWALL_LAKE_URI", uri)
    return uri


def test_lake_uri_is_required(monkeypatch, capsys):
    monkeypatch.delenv("PITWALL_LAKE_URI", raising=False)
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", "--latest"])
    assert exit_info.value.code == 2
    assert "PITWALL_LAKE_URI" in capsys.readouterr().err


def test_seasons_before_openf1_coverage_are_rejected(lake_env, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", "--season", "2022"])
    assert exit_info.value.code == 2
    assert "2023" in capsys.readouterr().err


def test_exactly_one_selector_is_required(lake_env):
    with pytest.raises(SystemExit):
        main(["ingest"])
    with pytest.raises(SystemExit):
        main(["ingest", "--latest", "--season", "2024"])


def test_ingest_meeting_end_to_end(lake_env, fixture_client):
    now = datetime(2025, 4, 1, tzinfo=UTC)
    assert main(["ingest", "--meeting", "1255"], client=fixture_client, now=now) == 0
    assert Lake(lake_env).markers() == {1255}
