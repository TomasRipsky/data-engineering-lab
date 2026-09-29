"""pitwall command line: `pitwall ingest --latest | --meeting KEY | --season YEAR`."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import UTC, datetime

from pitwall.client import OpenF1Client
from pitwall.ingest import ingest_latest, ingest_one, ingest_season
from pitwall.lake import Lake

FIRST_SEASON = 2023  # OpenF1 historical coverage starts here
log = logging.getLogger("pitwall")


def main(
    argv: list[str] | None = None,
    *,
    client: OpenF1Client | None = None,
    now: datetime | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="pitwall", description="F1 race-strategy pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="pull OpenF1 data into the raw lake")
    selector = ingest.add_mutually_exclusive_group(required=True)
    selector.add_argument(
        "--latest", action="store_true", help="finished meetings not yet in the lake"
    )
    selector.add_argument("--meeting", type=int, metavar="MEETING_KEY", help="one Grand Prix")
    selector.add_argument("--season", type=int, metavar="YEAR", help="backfill a whole season")
    args = parser.parse_args(argv)

    if args.season is not None and args.season < FIRST_SEASON:
        parser.error(f"OpenF1 has data from {FIRST_SEASON} onwards")
    lake_uri = os.environ.get("PITWALL_LAKE_URI")
    if not lake_uri:
        parser.error("PITWALL_LAKE_URI is not set (a path, file:// or gs:// URI)")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    lake = Lake(lake_uri)
    client = client or OpenF1Client()
    now = now or datetime.now(UTC)

    if args.latest:
        done = ingest_latest(client, lake, now)
    elif args.meeting is not None:
        done = ingest_one(client, lake, args.meeting, now)
    else:
        done = ingest_season(client, lake, args.season, now)
    log.info(
        "ingested %d meeting(s) %s using %d requests",
        len(done),
        done,
        client.request_count,
    )
    return 0
