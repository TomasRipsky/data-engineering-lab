import httpx
import pytest

from pitwall.client import NO_RESULTS, RateLimiter, backoff_delay


def test_rate_limiter_spaces_consecutive_calls():
    now = [100.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(2.1, clock=lambda: now[0], sleep=sleep)
    limiter.wait()  # first call never waits
    limiter.wait()  # immediately after: waits the full interval
    now[0] += 5
    limiter.wait()  # enough time has passed: no wait
    assert sleeps == [pytest.approx(2.1)]


def test_backoff_prefers_retry_after_and_is_capped():
    assert backoff_delay(1, "7") == 7.0
    assert backoff_delay(1, "999") == 60.0
    assert backoff_delay(3, None, rng=lambda: 0.5) == 8.5
    assert backoff_delay(10, None, rng=lambda: 0.0) == 60.0
    assert backoff_delay(1, "Wed, 21 Oct 2026 07:28:00 GMT", rng=lambda: 0.0) == 2.0


def test_get_sends_params_and_returns_rows(make_client):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=[{"lap_number": 1}])

    client = make_client(handler)
    assert client.get("laps", session_key=9998) == [{"lap_number": 1}]
    assert seen == ["https://api.openf1.org/v1/laps?session_key=9998"]
    assert client.request_count == 1


def test_no_results_404_means_empty(make_client):
    client = make_client(lambda request: httpx.Response(404, json=NO_RESULTS))
    assert client.get("pit", session_key=7953) == []


def test_any_other_404_fails(make_client):
    client = make_client(lambda request: httpx.Response(404, text="Not Found"))
    with pytest.raises(httpx.HTTPStatusError):
        client.get("lapz", session_key=1)


def test_retries_429_and_5xx_honouring_retry_after(make_client):
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(503),
            httpx.Response(200, json=[]),
        ]
    )
    sleeps = []
    client = make_client(lambda request: next(responses), sleeps)
    assert client.get("laps", session_key=1) == []
    assert sleeps[0] == 3.0
    assert len(sleeps) == 2
    assert client.request_count == 3


def test_gives_up_after_max_attempts(make_client):
    sleeps = []
    client = make_client(lambda request: httpx.Response(500), sleeps, max_attempts=3)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("laps", session_key=1)
    assert len(sleeps) == 2


def test_transport_errors_are_retried(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectTimeout("slow network", request=request)
        return httpx.Response(200, json=[{"ok": True}])

    assert make_client(handler).get("laps", session_key=1) == [{"ok": True}]


def test_client_errors_are_not_retried(make_client):
    sleeps = []
    client = make_client(lambda request: httpx.Response(400), sleeps)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("laps", session_key=1)
    assert sleeps == []


def test_non_list_body_fails(make_client):
    client = make_client(lambda request: httpx.Response(200, json={"detail": "odd"}))
    with pytest.raises(ValueError, match="expected a JSON list"):
        client.get("laps", session_key=1)
