"""Record trimmed OpenF1 responses for the integration tests. Dev tool: hits the real API.

Run from projects/pitwall:  uv run python tests/record_fixtures.py
"""

import json

from conftest import FIXTURES, fixture_name

from pitwall.client import OpenF1Client
from pitwall.contracts import MEETING_ENDPOINTS, SESSION_ENDPOINTS

MEETING, YEAR, SESSIONS = 1255, 2025, (9993, 9998)  # 2025 Chinese GP: Sprint + Race
DRIVERS = {4, 81}  # the two McLarens (Norris, Piastri) keep the fixtures small
DRIVER_FIELDS = ("driver_number", "overtaking_driver_number", "overtaken_driver_number")

REQUESTS = [
    ("meetings", {"meeting_key": MEETING}),
    ("meetings", {"year": YEAR}),
    ("sessions", {"year": YEAR}),
    *[(endpoint, {"session_key": key}) for key in SESSIONS for endpoint in SESSION_ENDPOINTS],
    *[(endpoint, {"meeting_key": MEETING}) for endpoint in MEETING_ENDPOINTS],
]


def keep(row: dict) -> bool:
    if row.get("meeting_key", MEETING) != MEETING:
        return False
    drivers = {row.get(field) for field in DRIVER_FIELDS} - {None}
    return not drivers or bool(drivers & DRIVERS)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for stale in FIXTURES.glob("*.json"):  # an endpoint that is empty now must lose its file
        stale.unlink()
    client = OpenF1Client()
    for endpoint, params in REQUESTS:
        rows = [row for row in client.get(endpoint, **params) if keep(row)]
        if rows:  # absent file = 404 "No results found." in the fake transport
            path = FIXTURES / fixture_name(endpoint, params)
            path.write_text(json.dumps(rows, indent=1) + "\n")
        print(f"{endpoint} {params}: {len(rows)} rows")


if __name__ == "__main__":
    main()
