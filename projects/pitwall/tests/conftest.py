import httpx
import pytest

from pitwall.client import BASE_URL, OpenF1Client


@pytest.fixture
def make_client():
    """Build an OpenF1Client over a fake transport, with no real waiting."""

    def build(handler, sleeps=None, max_attempts=5):
        http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
        sleep = sleeps.append if sleeps is not None else (lambda seconds: None)
        return OpenF1Client(http, min_interval=0, max_attempts=max_attempts, sleep=sleep)

    return build
