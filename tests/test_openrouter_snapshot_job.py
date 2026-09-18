from __future__ import annotations

from pathlib import Path

from openrouter_savings.snapshot_job import CATALOG_PROVIDER_LABEL, snapshot_catalog
from openrouter_savings.storage import Store


class FakeCatalogClient:
    def __init__(self, models: list[dict]) -> None:
        self._models = models
        self.list_models_calls = 0

    def list_models(self) -> list[dict]:
        self.list_models_calls += 1
        return self._models


def _models() -> list[dict]:
    return [
        {"id": "openai/gpt-4o", "pricing": {"prompt": "0.000005", "completion": "0.00002"}},
        {"id": "anthropic/claude-sonnet-5", "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        {"id": "no-pricing/model"},  # should be skipped, not crash
    ]


def test_snapshot_catalog_records_one_snapshot_per_priced_model(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    client = FakeCatalogClient(_models())

    result = snapshot_catalog(store, client, timestamp="2026-01-01T00:00:00+00:00")

    assert result["models_recorded"] == 2
    snapshots = store.price_snapshots.all()
    assert len(snapshots) == 2
    assert all(s.provider == CATALOG_PROVIDER_LABEL for s in snapshots)
    assert {s.model for s in snapshots} == {"openai/gpt-4o", "anthropic/claude-sonnet-5"}


def test_snapshot_catalog_skips_when_run_too_soon_after_last_snapshot(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    client = FakeCatalogClient(_models())

    snapshot_catalog(store, client, timestamp="2026-01-01T00:00:00+00:00")
    result = snapshot_catalog(
        store, client, timestamp="2026-01-01T00:30:00+00:00", min_interval_minutes=60
    )

    assert result.get("skipped_recent") is True
    assert client.list_models_calls == 1  # second call didn't hit the API at all
    assert len(store.price_snapshots.all()) == 2  # no duplicate rows added


def test_snapshot_catalog_runs_again_after_the_interval_elapses(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    client = FakeCatalogClient(_models())

    snapshot_catalog(store, client, timestamp="2026-01-01T00:00:00+00:00")
    result = snapshot_catalog(
        store, client, timestamp="2026-01-01T02:00:00+00:00", min_interval_minutes=60
    )

    assert result["models_recorded"] == 2
    assert len(store.price_snapshots.all()) == 4
