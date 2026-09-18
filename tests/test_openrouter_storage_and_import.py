from __future__ import annotations

from pathlib import Path

import pytest

from openrouter_savings.csv_import import CsvImportError, parse_price_history_csv_text
from openrouter_savings.models import DowntimeIncident, UsageEntry
from openrouter_savings.storage import Store


def test_store_round_trips_usage_entries(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    entry = UsageEntry(
        model="openai/gpt-4o",
        provider_used="openai-direct",
        timestamp="2026-01-01T00:00:00+00:00",
        prompt_tokens=10,
        completion_tokens=20,
        actual_cost=0.01,
    )
    store.usage.append(entry)

    reloaded = Store(tmp_path / "data")
    all_entries = reloaded.usage.all()
    assert len(all_entries) == 1
    assert all_entries[0].model == "openai/gpt-4o"
    assert all_entries[0].id == entry.id


def test_store_remove_by_id(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    entry = UsageEntry(
        model="m", provider_used="p", timestamp="2026-01-01T00:00:00+00:00", actual_cost=1.0
    )
    store.usage.append(entry)

    assert store.usage.remove_by_id(entry.id) is True
    assert store.usage.all() == []
    assert store.usage.remove_by_id("missing") is False


def test_store_round_trips_downtime_incidents(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    incident = DowntimeIncident(
        model="openai/gpt-4o", provider="openai", start="2026-01-01T00:00:00+00:00",
        end="2026-01-01T01:00:00+00:00", notes="outage",
    )
    store.downtime_incidents.append(incident)

    reloaded = Store(tmp_path / "data")
    all_incidents = reloaded.downtime_incidents.all()
    assert len(all_incidents) == 1
    assert all_incidents[0].notes == "outage"


def test_parse_price_history_csv_text() -> None:
    csv_text = (
        "model,provider,prompt_price,completion_price,effective_date\n"
        "openai/gpt-4o,azure,0.0000025,0.00001,2026-01-01\n"
    )
    snapshots = parse_price_history_csv_text(csv_text)
    assert len(snapshots) == 1
    assert snapshots[0].model == "openai/gpt-4o"
    assert snapshots[0].source == "import"
    assert snapshots[0].prompt_price == 0.0000025


def test_parse_price_history_csv_text_rejects_missing_columns() -> None:
    with pytest.raises(CsvImportError):
        parse_price_history_csv_text("model,provider\nopenai/gpt-4o,azure\n")


def test_parse_price_history_csv_text_rejects_bad_row() -> None:
    csv_text = (
        "model,provider,prompt_price,completion_price,effective_date\n"
        "openai/gpt-4o,azure,not-a-number,0.00001,2026-01-01\n"
    )
    with pytest.raises(CsvImportError):
        parse_price_history_csv_text(csv_text)
