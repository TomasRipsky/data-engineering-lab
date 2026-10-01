# Recorded OpenF1 responses

Real API answers for the 2025 Chinese GP (meeting 1255, drivers 4 and 81), replayed by `tests/conftest.py` so the tests run offline. File name = the request (`<endpoint>__<params>.json`); a missing file means "No results found".

Re-record when OpenF1 changes: `uv run python tests/record_fixtures.py` from `projects/pitwall`. The full explanation and the update procedure are in [docs/guide.md](../../../docs/guide.md) ("Python tests and recorded API answers").
