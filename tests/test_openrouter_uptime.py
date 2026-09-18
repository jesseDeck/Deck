from __future__ import annotations

import pytest

from openrouter_savings.csv_import import CsvImportError, parse_downtime_incidents_csv_text
from openrouter_savings.models import DowntimeIncident, UptimeSnapshot
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
    assert len(summary.degraded_intervals) == 1  # the 50% interval is below the degraded threshold
    assert summary.logged_incident_minutes == 0.0


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


def test_summarize_uptime_includes_imported_incidents_separately_from_polled_downtime() -> None:
    snapshots = [
        UptimeSnapshot(model="m", provider="p", uptime_pct=100.0, timestamp="2026-01-01T00:00:00+00:00"),
        UptimeSnapshot(model="m", provider="p", uptime_pct=100.0, timestamp="2026-01-01T01:00:00+00:00"),
    ]
    incidents = [
        DowntimeIncident(model="m", provider="p", start="2025-06-01T00:00:00+00:00", end="2025-06-01T01:30:00+00:00"),
    ]

    summaries = summarize_uptime(snapshots, incidents)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.estimated_downtime_minutes == 0.0  # polled snapshots show 100% uptime throughout
    assert summary.logged_incident_minutes == 90.0
    assert len(summary.logged_incidents) == 1


def test_summarize_uptime_reports_a_key_with_only_imported_incidents_and_no_snapshots() -> None:
    incidents = [
        DowntimeIncident(model="m", provider="p", start="2025-06-01T00:00:00+00:00", end="2025-06-01T01:00:00+00:00"),
    ]
    summaries = summarize_uptime([], incidents)
    assert len(summaries) == 1
    assert summaries[0].latest_uptime_pct is None
    assert summaries[0].logged_incident_minutes == 60.0


def test_parse_downtime_incidents_csv_text() -> None:
    csv_text = (
        "model,provider,start,end,notes\n"
        "openai/gpt-4o,openai,2026-03-04T10:00:00+00:00,2026-03-04T11:30:00+00:00,partial outage\n"
    )
    incidents = parse_downtime_incidents_csv_text(csv_text)
    assert len(incidents) == 1
    assert incidents[0].model == "openai/gpt-4o"
    assert incidents[0].notes == "partial outage"
    assert incidents[0].source == "import"


def test_parse_downtime_incidents_csv_text_rejects_missing_columns() -> None:
    with pytest.raises(CsvImportError):
        parse_downtime_incidents_csv_text("model,provider\nopenai/gpt-4o,openai\n")
