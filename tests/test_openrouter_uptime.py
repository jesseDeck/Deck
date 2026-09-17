from __future__ import annotations

from openrouter_savings.models import UptimeSnapshot
from openrouter_savings.uptime import summarize_uptime


def test_summarize_uptime_computes_downtime_from_intervals() -> None:
    # Provider at 50% uptime for a 60-minute interval implies 30 minutes of downtime.
    snapshots = [
        UptimeSnapshot(model="m", provider="p", uptime_pct=50.0, timestamp="2026-01-01T00:00:00+00:00"),
        UptimeSnapshot(model="m", provider="p", uptime_pct=100.0, timestamp="2026-01-01T01:00:00+00:00"),
    ]

    summaries = summarize_uptime(snapshots)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.model == "m"
    assert summary.provider == "p"
    assert summary.latest_uptime_pct == 100.0
    assert summary.tracked_minutes == 60.0
    assert summary.estimated_downtime_minutes == 30.0
    assert len(summary.incidents) == 1  # the 50% interval is below the degraded threshold


def test_summarize_uptime_groups_by_model_and_provider() -> None:
    snapshots = [
        UptimeSnapshot(model="m1", provider="a", uptime_pct=100.0, timestamp="2026-01-01T00:00:00+00:00"),
        UptimeSnapshot(model="m1", provider="b", uptime_pct=100.0, timestamp="2026-01-01T00:00:00+00:00"),
        UptimeSnapshot(model="m2", provider="a", uptime_pct=100.0, timestamp="2026-01-01T00:00:00+00:00"),
    ]
    summaries = summarize_uptime(snapshots)
    keys = {(s.model, s.provider) for s in summaries}
    assert keys == {("m1", "a"), ("m1", "b"), ("m2", "a")}


def test_summarize_uptime_handles_unknown_uptime_gracefully() -> None:
    snapshots = [
        UptimeSnapshot(model="m", provider="p", uptime_pct=None, timestamp="2026-01-01T00:00:00+00:00"),
    ]
    summaries = summarize_uptime(snapshots)
    assert summaries[0].latest_uptime_pct is None
    assert summaries[0].average_uptime_pct is None
    assert summaries[0].estimated_downtime_minutes == 0.0
