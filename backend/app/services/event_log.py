"""Bounded local operational events with no arbitrary message or credential fields."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# The viewer displays only these codes; exception messages and URLs never enter the file.
EVENT_LEVELS = {
    "runtime_started": "INFO",
    "runtime_stopped": "INFO",
    "scan_succeeded": "INFO",
    "scan_partial": "WARNING",
    "scan_failed": "ERROR",
    "server_failed": "ERROR",
    "scheduler_failed": "ERROR",
    "delivery_sent": "INFO",
    "delivery_retry": "WARNING",
    "delivery_failed": "ERROR",
    "delivery_recovered": "WARNING",
}
LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class EventLog:
    """Store only enumerated events; retain at most five bounded log files."""

    def __init__(self, directory: Path, *, max_bytes: int = 1_000_000, backups: int = 4) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self._path = directory / "events.jsonl"
        self._backups = backups
        self._handler = RotatingFileHandler(self._path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8", delay=True)
        self._handler.setFormatter(logging.Formatter("%(message)s"))

    def close(self) -> None:
        self._handler.close()

    def write(self, code: str, *, server_id: int | None = None, library_id: int | None = None) -> None:
        """Reject unrecognized codes and invalid IDs rather than accepting arbitrary text."""

        if code not in EVENT_LEVELS or any(
            value is not None and (type(value) is not int or value <= 0) for value in (server_id, library_id)
        ):
            raise ValueError("Invalid operational event")
        entry = {
            "at": datetime.now(UTC).isoformat(),
            "level": EVENT_LEVELS[code],
            "code": code,
            "server_id": server_id,
            "library_id": library_id,
        }
        record = logging.LogRecord("bookorbit.events", logging.INFO, "", 0, json.dumps(entry, separators=(",", ":")), (), None)
        self._handler.handle(record)

    def list_entries(
        self,
        *,
        level: str | None = None,
        server_id: int | None = None,
        library_id: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Read newest first, validating each line and never returning untrusted fields."""

        if level is not None and level not in LEVELS:
            raise ValueError("Invalid log level")
        entries: list[dict[str, Any]] = []
        # Hold the handler lock so rotation cannot rename a file during this bounded read.
        self._handler.acquire()
        try:
            for suffix in range(0, self._backups + 1):
                path = self._path if suffix == 0 else self._path.with_name(f"{self._path.name}.{suffix}")
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                except (FileNotFoundError, UnicodeError):
                    continue
                for line in reversed(lines):
                    entry = _safe_entry(line)
                    if entry is None:
                        continue
                    day = datetime.fromisoformat(entry["at"]).astimezone(UTC).date()
                    if (
                        (level is not None and entry["level"] != level)
                        or (server_id is not None and entry["server_id"] != server_id)
                        or (library_id is not None and entry["library_id"] != library_id)
                        or (from_date is not None and day < from_date)
                        or (to_date is not None and day > to_date)
                    ):
                        continue
                    entries.append(entry)
                    if len(entries) > offset + limit:
                        return {"items": entries[offset : offset + limit], "has_more": True}
        finally:
            self._handler.release()
        return {"items": entries[offset : offset + limit], "has_more": False}


def _safe_entry(line: str) -> dict[str, Any] | None:
    """Reconstruct an allowlisted response even if a local log file is malformed."""

    try:
        value = json.loads(line)
        if not isinstance(value, dict) or value.get("code") not in EVENT_LEVELS:
            return None
        code = value["code"]
        timestamp = datetime.fromisoformat(value["at"])
        if timestamp.tzinfo is None or value.get("level") != EVENT_LEVELS[code]:
            return None
        ids = [value.get("server_id"), value.get("library_id")]
        if any(item is not None and (type(item) is not int or item <= 0) for item in ids):
            return None
        return {
            "at": timestamp.astimezone(UTC).isoformat(),
            "level": EVENT_LEVELS[code],
            "code": code,
            "server_id": ids[0],
            "library_id": ids[1],
        }
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
