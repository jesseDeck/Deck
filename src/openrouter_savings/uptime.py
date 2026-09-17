"""Downtime estimation from polled uptime snapshots.

OpenRouter doesn't expose a historical downtime log through its public API,
so this only ever knows what it has itself observed: each time
``snapshot_job.take_snapshot`` runs, it records the current uptime percentage
OpenRouter reports for each tracked model/provider. Between two consecutive
snapshots, we treat the *earlier* snapshot's uptime percentage as the
fraction of that interval the provider was up -- a linear approximation, not
a certified log of every outage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import UptimeSnapshot

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
    incidents: list[dict[str, Any]] = field(default_factory=list)

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
            "incidents": self.incidents,
        }


def summarize_uptime(
    snapshots: list[UptimeSnapshot], *, degraded_threshold_pct: float = DEGRADED_THRESHOLD_PCT
) -> list[ProviderUptimeSummary]:
    """Build a downtime summary per (model, provider) from stored snapshots."""
    by_key: dict[tuple[str, str], list[UptimeSnapshot]] = {}
    for snap in snapshots:
        by_key.setdefault((snap.model, snap.provider), []).append(snap)

    summaries: list[ProviderUptimeSummary] = []
    for (model, provider), snaps in by_key.items():
        snaps.sort(key=lambda s: s.timestamp)
        known = [s.uptime_pct for s in snaps if s.uptime_pct is not None]
        latest = known[-1] if known else None
        average = sum(known) / len(known) if known else None

        downtime_minutes = 0.0
        tracked_minutes = 0.0
        incidents: list[dict[str, Any]] = []
        for prev, curr in zip(snaps, snaps[1:]):
            interval_minutes = (_parse(curr.timestamp) - _parse(prev.timestamp)).total_seconds() / 60.0
            if interval_minutes <= 0:
                continue
            tracked_minutes += interval_minutes
            if prev.uptime_pct is not None:
                downtime_minutes += interval_minutes * (1 - prev.uptime_pct / 100.0)
                if prev.uptime_pct < degraded_threshold_pct:
                    incidents.append(
                        {
                            "from": prev.timestamp,
                            "to": curr.timestamp,
                            "uptime_pct": prev.uptime_pct,
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
                incidents=incidents,
            )
        )

    summaries.sort(key=lambda s: (s.model, s.provider))
    return summaries
