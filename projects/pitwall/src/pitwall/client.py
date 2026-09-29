"""HTTP client for the OpenF1 API: polite rate limiting, retries, and 404-as-empty."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import Any

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1"
NO_RESULTS = {"detail": "No results found."}  # OpenF1's answer when a filter matches nothing
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_DELAY = 60.0


class RateLimiter:
    """Guarantees at least `min_interval` seconds between consecutive `wait()` calls."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self._last + self.min_interval - now
            if remaining > 0:
                self._sleep(remaining)
                now += remaining
        self._last = now


def backoff_delay(
    attempt: int, retry_after: str | None, rng: Callable[[], float] = random.random
) -> float:
    """Seconds to wait before retrying after failed `attempt` (1-based).

    Honours a numeric Retry-After header; otherwise exponential backoff with jitter.
    """
    if retry_after is not None:
        try:
            return min(float(retry_after), MAX_DELAY)
        except ValueError:
            pass  # HTTP-date form: fall back to our own backoff
    return min(2.0**attempt + rng(), MAX_DELAY)


def _is_no_results(response: httpx.Response) -> bool:
    try:
        return response.json() == NO_RESULTS
    except ValueError:
        return False


class OpenF1Client:
    def __init__(
        self,
        http: httpx.Client | None = None,
        *,
        min_interval: float = 2.1,  # 30 req/min free-tier limit, with a margin
        max_attempts: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=30.0)
        self._limiter = RateLimiter(min_interval, clock=clock, sleep=sleep)
        self._sleep = sleep
        self.max_attempts = max_attempts
        self.request_count = 0

    def get(self, endpoint: str, **params: Any) -> list[dict[str, Any]]:
        """Return all rows of `endpoint` matching `params`; [] when OpenF1 has none."""
        for attempt in range(1, self.max_attempts + 1):
            self._limiter.wait()
            self.request_count += 1
            try:
                response = self._http.get(f"/{endpoint}", params=params)
            except httpx.TransportError as exc:
                if attempt == self.max_attempts:
                    raise
                self._retry(endpoint, params, attempt, str(exc), None)
                continue
            if response.status_code in RETRYABLE_STATUS and attempt < self.max_attempts:
                reason = f"HTTP {response.status_code}"
                self._retry(
                    endpoint,
                    params,
                    attempt,
                    reason,
                    response.headers.get("Retry-After"),
                )
                continue
            if response.status_code == 404 and _is_no_results(response):
                return []
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError(f"{endpoint} {params}: expected a JSON list, got {rows!r:.100}")
            return rows
        raise AssertionError("unreachable")

    def _retry(self, endpoint, params, attempt, reason, retry_after) -> None:
        delay = backoff_delay(attempt, retry_after)
        log.warning("%s %s: %s; retry %d in %.1fs", endpoint, params, reason, attempt, delay)
        self._sleep(delay)
