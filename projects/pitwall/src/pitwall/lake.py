"""The raw lake: Parquet files and success markers under one root (local path, file:// or gs://).

A meeting is visible to downstream steps only once its success marker exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs

MARKERS_DIR = "raw/_success"


def season_file(endpoint: str, season: int) -> str:
    return f"raw/{endpoint}/season={season}/part.parquet"


def meeting_file(endpoint: str, season: int, meeting_key: int) -> str:
    return f"raw/{endpoint}/season={season}/meeting_key={meeting_key}/part.parquet"


def marker_file(season: int, meeting_key: int) -> str:
    return f"{MARKERS_DIR}/season={season}/meeting_key={meeting_key}.json"


def _resolve(uri: str) -> tuple[fs.FileSystem, str]:
    parsed = urlparse(uri)
    if parsed.scheme in (
        "",
        "file",
    ):  # plain paths may contain spaces; URIs may hold %20
        path = unquote(parsed.path) if parsed.scheme else uri
        return fs.LocalFileSystem(), str(Path(path).resolve())
    return fs.FileSystem.from_uri(uri)


class Lake:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self._fs, self._root = _resolve(uri.rstrip("/"))

    def _path(self, rel: str) -> str:
        return f"{self._root}/{rel}"

    def _prepare(self, rel: str) -> str:
        path = self._path(rel)
        self._fs.create_dir(path.rsplit("/", 1)[0], recursive=True)
        return path

    def write_table(self, rel: str, table: pa.Table) -> None:
        pq.write_table(table, self._prepare(rel), filesystem=self._fs)

    def read_table(self, rel: str) -> pa.Table:
        # Read through a file handle so pyarrow does not infer hive partition columns.
        with self._fs.open_input_file(self._path(rel)) as handle:
            return pq.read_table(handle)

    def write_json(self, rel: str, obj: Any) -> None:
        with self._fs.open_output_stream(self._prepare(rel)) as handle:
            handle.write(json.dumps(obj, indent=2, sort_keys=True).encode())

    def read_json(self, rel: str) -> Any:
        with self._fs.open_input_stream(self._path(rel)) as handle:
            return json.loads(handle.read())

    def exists(self, rel: str) -> bool:
        return self._fs.get_file_info(self._path(rel)).type != fs.FileType.NotFound

    def delete(self, rel: str) -> None:
        if self.exists(rel):
            self._fs.delete_file(self._path(rel))

    def markers(self) -> set[int]:
        """Meeting keys whose ingestion completed (a success marker exists)."""
        selector = fs.FileSelector(self._path(MARKERS_DIR), recursive=True, allow_not_found=True)
        return {
            int(info.base_name.removeprefix("meeting_key=").removesuffix(".json"))
            for info in self._fs.get_file_info(selector)
            if info.type == fs.FileType.File and info.base_name.endswith(".json")
        }
