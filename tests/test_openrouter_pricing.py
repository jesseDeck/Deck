from __future__ import annotations

from openrouter_savings.models import PriceSnapshot, UsageEntry
from openrouter_savings.pricing import actual_cost, cheapest_snapshot_at_or_before


def test_actual_cost_prefers_explicit_value() -> None:
    entry = UsageEntry(
        model="openai/gpt-4o",
        provider_used="openai-direct",
        timestamp="2026-01-01T00:00:00+00:00",
        prompt_tokens=1000,
        completion_tokens=500,
        actual_cost=1.23,
        unit_prompt_price=999,  # should be ignored since actual_cost is set
    )
    assert actual_cost(entry) == 1.23


def test_actual_cost_derives_from_unit_prices() -> None:
    entry = UsageEntry(
        model="openai/gpt-4o",
        provider_used="openai-direct",
        timestamp="2026-01-01T00:00:00+00:00",
        prompt_tokens=1000,
        completion_tokens=500,
        unit_prompt_price=0.000005,
        unit_completion_price=0.00001,
    )
    assert actual_cost(entry) == 1000 * 0.000005 + 500 * 0.00001


def test_cheapest_snapshot_picks_lowest_cost_for_actual_token_mix() -> None:
    # provider A is cheaper on prompt tokens, provider B cheaper on completion tokens.
    snapshots = [
        PriceSnapshot(
            model="m", provider="a", prompt_price=0.000001, completion_price=0.00002,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
        PriceSnapshot(
            model="m", provider="b", prompt_price=0.00001, completion_price=0.000002,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
    ]

    # Prompt-heavy workload should favor provider A.
    chosen, estimated = cheapest_snapshot_at_or_before(
        snapshots, "m", "2026-06-01T00:00:00+00:00", prompt_tokens=100000, completion_tokens=10
    )
    assert chosen.provider == "a"
    assert estimated is False

    # Completion-heavy workload should favor provider B.
    chosen, _ = cheapest_snapshot_at_or_before(
        snapshots, "m", "2026-06-01T00:00:00+00:00", prompt_tokens=10, completion_tokens=100000
    )
    assert chosen.provider == "b"


def test_cheapest_snapshot_uses_latest_price_at_or_before_cutoff() -> None:
    snapshots = [
        PriceSnapshot(model="m", provider="a", prompt_price=0.00001, completion_price=0.00001,
                      timestamp="2026-01-01T00:00:00+00:00"),
        PriceSnapshot(model="m", provider="a", prompt_price=0.000001, completion_price=0.000001,
                      timestamp="2026-03-01T00:00:00+00:00"),
        PriceSnapshot(model="m", provider="a", prompt_price=0.0000001, completion_price=0.0000001,
                      timestamp="2026-06-01T00:00:00+00:00"),  # after the cutoff, should be ignored
    ]

    chosen, estimated = cheapest_snapshot_at_or_before(
        snapshots, "m", "2026-04-01T00:00:00+00:00", prompt_tokens=100, completion_tokens=100
    )
    assert chosen.timestamp == "2026-03-01T00:00:00+00:00"
    assert estimated is False


def test_cheapest_snapshot_falls_back_to_earliest_when_all_snapshots_are_later() -> None:
    snapshots = [
        PriceSnapshot(model="m", provider="a", prompt_price=0.00001, completion_price=0.00001,
                      timestamp="2026-06-01T00:00:00+00:00"),
    ]
    chosen, estimated = cheapest_snapshot_at_or_before(
        snapshots, "m", "2026-01-01T00:00:00+00:00", prompt_tokens=100, completion_tokens=100
    )
    assert chosen is not None
    assert estimated is True


def test_cheapest_snapshot_returns_none_when_model_unknown() -> None:
    chosen, estimated = cheapest_snapshot_at_or_before(
        [], "unknown/model", "2026-01-01T00:00:00+00:00", prompt_tokens=1, completion_tokens=1
    )
    assert chosen is None
    assert estimated is False
