"""Local JSON-file storage for usage entries and polled snapshots.

No database dependency is needed for a single-user local tool: each list is
just a JSON array on disk, read fully into memory and rewritten on change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Callable, Generic, TypeVar

from .models import DowntimeIncident, PriceSnapshot, TrackedModel, UsageEntry, UptimeSnapshot

T = TypeVar("T")


class JsonListStore(Generic[T]):
    """A file-backed list of records, safe for single-process concurrent use."""

    def __init__(self, path: Path, to_dict: Callable[[T], dict], from_dict: Callable[[dict], T]):
        self._path = path
        self._to_dict = to_dict
        self._from_dict = from_dict
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]")

    def all(self) -> list[T]:
        with self._lock:
            return self._read()

    def append(self, record: T) -> None:
        with self._lock:
            records = self._read()
            records.append(record)
            self._write(records)

    def replace_all(self, records: list[T]) -> None:
        with self._lock:
            self._write(records)

    def remove_by_id(self, record_id: str) -> bool:
        with self._lock:
            records = self._read()
            kept = [r for r in records if getattr(r, "id", None) != record_id]
            removed = len(kept) != len(records)
            if removed:
                self._write(kept)
            return removed

    def _read(self) -> list[T]:
        try:
            raw = json.loads(self._path.read_text() or "[]")
        except json.JSONDecodeError:
            raw = []
        return [self._from_dict(item) for item in raw]

    def _write(self, records: list[T]) -> None:
        payload = [self._to_dict(r) for r in records]
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2))
        os.replace(tmp_path, self._path)


class Store:
    """Bundles the on-disk stores this tool needs, rooted at one data directory."""

    def __init__(self, data_dir: str | Path = ".openrouter_savings"):
        self.data_dir = Path(data_dir)
        self.usage = JsonListStore[UsageEntry](
            self.data_dir / "usage.json", UsageEntry.to_dict, UsageEntry.from_dict
        )
        self.price_snapshots = JsonListStore[PriceSnapshot](
            self.data_dir / "price_snapshots.json", PriceSnapshot.to_dict, PriceSnapshot.from_dict
        )
        self.uptime_snapshots = JsonListStore[UptimeSnapshot](
            self.data_dir / "uptime_snapshots.json", UptimeSnapshot.to_dict, UptimeSnapshot.from_dict
        )
        self.tracked_models = JsonListStore[TrackedModel](
            self.data_dir / "tracked_models.json", TrackedModel.to_dict, TrackedModel.from_dict
        )
        self.downtime_incidents = JsonListStore[DowntimeIncident](
            self.data_dir / "downtime_incidents.json", DowntimeIncident.to_dict, DowntimeIncident.from_dict
        )
