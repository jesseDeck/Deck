from __future__ import annotations

from openrouter_savings.models import PriceSnapshot, UsageEntry
from openrouter_savings.savings import compute_savings


def _entry(**overrides) -> UsageEntry:
    defaults = dict(
        model="openai/gpt-4o",
        provider_used="openai-direct",
        timestamp="2026-02-01T00:00:00+00:00",
        prompt_tokens=1000,
        completion_tokens=1000,
        actual_cost=0.02,
    )
    defaults.update(overrides)
    return UsageEntry(**defaults)


def test_compute_savings_totals_and_per_entry_result() -> None:
    entries = [_entry()]
    snapshots = [
        PriceSnapshot(
            model="openai/gpt-4o", provider="azure", prompt_price=0.000005, completion_price=0.000005,
            timestamp="2026-01-01T00:00:00+00:00",
        )
    ]

    report = compute_savings(entries, snapshots)

    assert report.total_actual == 0.02
    assert report.total_best_openrouter == 1000 * 0.000005 + 1000 * 0.000005
    assert report.total_savings == report.total_actual - report.total_best_openrouter
    assert report.entries_missing_price_data == 0
    assert report.results[0].best_openrouter_provider == "azure"


def test_compute_savings_flags_entries_with_no_price_data() -> None:
    entries = [_entry(model="unknown/model")]
    report = compute_savings(entries, [])

    assert report.entries_missing_price_data == 1
    assert report.results[0].best_openrouter_cost is None
    assert report.results[0].savings is None
    # with no comparison available, the missing entry is counted break-even, not a loss.
    assert report.total_best_openrouter == report.total_actual


def test_compute_savings_aggregates_by_model_and_provider_used() -> None:
    entries = [
        _entry(model="openai/gpt-4o", provider_used="openai-direct", actual_cost=0.03),
        _entry(model="anthropic/claude-sonnet-5", provider_used="anthropic-direct", actual_cost=0.05),
    ]
    snapshots = [
        PriceSnapshot(model="openai/gpt-4o", provider="azure", prompt_price=0.000001, completion_price=0.000001,
                      timestamp="2026-01-01T00:00:00+00:00"),
        PriceSnapshot(model="anthropic/claude-sonnet-5", provider="bedrock", prompt_price=0.000002,
                      completion_price=0.000002, timestamp="2026-01-01T00:00:00+00:00"),
    ]

    report = compute_savings(entries, snapshots)

    assert set(report.by_model) == {"openai/gpt-4o", "anthropic/claude-sonnet-5"}
    assert set(report.by_provider_used) == {"openai-direct", "anthropic-direct"}
    assert report.by_model["openai/gpt-4o"]["actual"] == 0.03


def test_compute_savings_routes_to_cheaper_acceptable_substitute() -> None:
    entry = _entry(
        model="expensive/model", actual_cost=1.0,
        acceptable_models=["cheap/model"],
    )
    snapshots = [
        PriceSnapshot(model="expensive/model", provider="p1", prompt_price=0.0001, completion_price=0.0001,
                      timestamp="2026-01-01T00:00:00+00:00"),
        PriceSnapshot(model="cheap/model", provider="p2", prompt_price=0.000001, completion_price=0.000001,
                      timestamp="2026-01-01T00:00:00+00:00"),
    ]

    report = compute_savings([entry], snapshots)

    result = report.results[0]
    assert result.best_openrouter_model == "cheap/model"
    assert result.best_openrouter_provider == "p2"
    as_dict = report.to_dict()["entries"][0]
    assert as_dict["routed_to_different_model"] is True


def test_compute_savings_default_entry_does_not_cross_route() -> None:
    # An entry with no acceptable_models/any_model_acceptable set (the pre-existing default)
    # should behave exactly as before: only ever compare providers of its own model.
    entry = _entry(model="expensive/model", actual_cost=1.0)
    snapshots = [
        PriceSnapshot(model="expensive/model", provider="p1", prompt_price=0.0001, completion_price=0.0001,
                      timestamp="2026-01-01T00:00:00+00:00"),
        PriceSnapshot(model="cheap/model", provider="p2", prompt_price=0.000001, completion_price=0.000001,
                      timestamp="2026-01-01T00:00:00+00:00"),
    ]

    report = compute_savings([entry], snapshots)

    assert report.results[0].best_openrouter_model == "expensive/model"


def test_compute_savings_builds_daily_timeseries() -> None:
    entries = [
        _entry(timestamp="2026-02-01T09:00:00+00:00", actual_cost=0.01),
        _entry(timestamp="2026-02-01T15:00:00+00:00", actual_cost=0.02),
        _entry(timestamp="2026-02-02T09:00:00+00:00", actual_cost=0.03),
    ]
    report = compute_savings(entries, [])

    dates = [point["date"] for point in report.timeseries]
    assert dates == ["2026-02-01", "2026-02-02"]
    assert report.timeseries[0]["actual"] == 0.03
