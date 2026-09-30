from pathlib import Path

import httpx
import pytest

from pitwall.client import BASE_URL, NO_RESULTS, OpenF1Client


@pytest.fixture
def make_client():
    """Build an OpenF1Client over a fake transport, with no real waiting."""

    def build(handler, sleeps=None, max_attempts=5):
        http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
        sleep = sleeps.append if sleeps is not None else (lambda seconds: None)
        return OpenF1Client(http, min_interval=0, max_attempts=max_attempts, sleep=sleep)

    return build


FIXTURES = Path(__file__).parent / "fixtures" / "openf1"


def fixture_name(endpoint: str, params: dict) -> str:
    query = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    return f"{endpoint}__{query}.json"


def _fixture_handler(request: httpx.Request) -> httpx.Response:
    endpoint = request.url.path.rsplit("/", 1)[-1]
    path = FIXTURES / fixture_name(endpoint, dict(request.url.params))
    if not path.exists():
        return httpx.Response(404, json=NO_RESULTS)
    return httpx.Response(
        200, content=path.read_bytes(), headers={"content-type": "application/json"}
    )


@pytest.fixture
def openf1_fixtures():
    """Transport handler serving recorded OpenF1 responses (404 'No results' otherwise)."""
    return _fixture_handler


@pytest.fixture
def fixture_client(make_client):
    return make_client(_fixture_handler)
