"""Downtime estimation from polled uptime snapshots and imported incident logs.

Two independent sources feed this, and they are kept separate rather than
summed (their windows can overlap, and summing would double-count):

- **Polled snapshots** (``UptimeSnapshot``): OpenRouter doesn't expose a
  historical downtime log through its public API, so this only knows what
  ``snapshot_job.take_snapshot`` has itself observed. Between two consecutive
  snapshots, we treat the *earlier* snapshot's uptime percentage as the
  fraction of that interval the provider was up -- a linear approximation,
  not a certified log of every outage.
- **Imported incidents** (``DowntimeIncident``): discrete outage windows
  backfilled from an external source (e.g. a status-monitoring site's
  incident export) via ``csv_import.parse_downtime_incidents_csv_text``.
  These can predate when you started polling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import DowntimeIncident, UptimeSnapshot

DEGRADED_THRESHOLD_PCT = 99.0


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@dataclass
class ProviderUptimeSummary:
    model: str
    provider: str
    latest_uptime_pct: float | None
    average_uptime_pct: float | None
    estimated_downtime_minutes: float
    tracked_minutes: float
    degraded_intervals: list[dict[str, Any]] = field(default_factory=list)
    logged_incident_minutes: float = 0.0
    logged_incidents: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "latest_uptime_pct": self.latest_uptime_pct,
            "average_uptime_pct": (
                round(self.average_uptime_pct, 3) if self.average_uptime_pct is not None else None
            ),
            "estimated_downtime_minutes": round(self.estimated_downtime_minutes, 2),
            "tracked_minutes": round(self.tracked_minutes, 2),
            "degraded_intervals": self.degraded_intervals,
            "logged_incident_minutes": round(self.logged_incident_minutes, 2),
            "logged_incidents": self.logged_incidents,
        }


def summarize_uptime(
    snapshots: list[UptimeSnapshot],
    incidents: list[DowntimeIncident] | None = None,
    *,
    degraded_threshold_pct: float = DEGRADED_THRESHOLD_PCT,
) -> list[ProviderUptimeSummary]:
    """Build a downtime summary per (model, provider) from stored snapshots and imported incidents."""
    by_key: dict[tuple[str, str], list[UptimeSnapshot]] = {}
    for snap in snapshots:
        by_key.setdefault((snap.model, snap.provider), []).append(snap)

    incidents_by_key: dict[tuple[str, str], list[DowntimeIncident]] = {}
    for incident in incidents or []:
        incidents_by_key.setdefault((incident.model, incident.provider), []).append(incident)

    all_keys = set(by_key) | set(incidents_by_key)
    summaries: list[ProviderUptimeSummary] = []
    for model, provider in all_keys:
        snaps = sorted(by_key.get((model, provider), []), key=lambda s: s.timestamp)
        known = [s.uptime_pct for s in snaps if s.uptime_pct is not None]
        latest = known[-1] if known else None
        average = sum(known) / len(known) if known else None

        downtime_minutes = 0.0
        tracked_minutes = 0.0
        degraded_intervals: list[dict[str, Any]] = []
        for prev, curr in zip(snaps, snaps[1:]):
            interval_minutes = (_parse(curr.timestamp) - _parse(prev.timestamp)).total_seconds() / 60.0
            if interval_minutes <= 0:
                continue
            tracked_minutes += interval_minutes
            if prev.uptime_pct is not None:
                downtime_minutes += interval_minutes * (1 - prev.uptime_pct / 100.0)
                if prev.uptime_pct < degraded_threshold_pct:
                    degraded_intervals.append(
                        {
                            "from": prev.timestamp,
                            "to": curr.timestamp,
                            "uptime_pct": prev.uptime_pct,
                        }
                    )

        logged = sorted(incidents_by_key.get((model, provider), []), key=lambda i: i.start)
        logged_minutes = 0.0
        logged_dicts: list[dict[str, Any]] = []
        for incident in logged:
            duration = (_parse(incident.end) - _parse(incident.start)).total_seconds() / 60.0
            if duration < 0:
                continue
            logged_minutes += duration
            logged_dicts.append(
                {
                    "start": incident.start,
                    "end": incident.end,
                    "minutes": round(duration, 2),
                    "source": incident.source,
                    "notes": incident.notes,
                }
            )

        summaries.append(
            ProviderUptimeSummary(
                model=model,
                provider=provider,
                latest_uptime_pct=latest,
                average_uptime_pct=average,
                estimated_downtime_minutes=downtime_minutes,
                tracked_minutes=tracked_minutes,
                degraded_intervals=degraded_intervals,
                logged_incident_minutes=logged_minutes,
                logged_incidents=logged_dicts,
            )
        )

    summaries.sort(key=lambda s: (s.model, s.provider))
    return summaries
