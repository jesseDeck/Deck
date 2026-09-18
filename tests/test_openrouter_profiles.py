from __future__ import annotations

from datetime import datetime, timezone

from openrouter_savings.models import ModelProfile
from openrouter_savings.profiles import profile_to_usage_entries, profiles_to_usage_entries


def test_profile_to_usage_entries_generates_one_entry_per_month() -> None:
    profile = ModelProfile(
        model="openai/gpt-4o",
        used_since="2026-01-15",
        used_until="2026-03-01",
        monthly_prompt_tokens=100000,
        monthly_completion_tokens=50000,
        monthly_cost=20.0,
    )

    entries = profile_to_usage_entries(profile)

    assert len(entries) == 3  # January, February, March
    assert all(e.model == "openai/gpt-4o" for e in entries)
    assert all(e.actual_cost == 20.0 for e in entries)
    assert all(e.prompt_tokens == 100000 for e in entries)
    assert [e.timestamp[:7] for e in entries] == ["2026-01", "2026-02", "2026-03"]


def test_profile_to_usage_entries_same_month_start_and_end_is_one_entry() -> None:
    profile = ModelProfile(model="m", used_since="2026-05-01", used_until="2026-05-20")
    entries = profile_to_usage_entries(profile)
    assert len(entries) == 1


def test_profile_to_usage_entries_defaults_end_to_now() -> None:
    profile = ModelProfile(model="m", used_since="2026-01-01")
    now = datetime(2026, 4, 15, tzinfo=timezone.utc)

    entries = profile_to_usage_entries(profile, now=now)

    assert len(entries) == 4  # Jan, Feb, Mar, Apr


def test_profile_to_usage_entries_propagates_routing_preferences() -> None:
    profile = ModelProfile(
        model="openai/gpt-4o",
        used_since="2026-01-01",
        used_until="2026-01-10",
        acceptable_models=["anthropic/claude-sonnet-5"],
        any_model_acceptable=False,
    )
    entries = profile_to_usage_entries(profile)
    assert entries[0].acceptable_models == ["anthropic/claude-sonnet-5"]
    assert entries[0].any_model_acceptable is False


def test_profiles_to_usage_entries_combines_multiple_profiles() -> None:
    profiles = [
        ModelProfile(model="a", used_since="2026-01-01", used_until="2026-01-10"),
        ModelProfile(model="b", used_since="2026-02-01", used_until="2026-02-10"),
    ]
    entries = profiles_to_usage_entries(profiles)
    assert len(entries) == 2
    assert {e.model for e in entries} == {"a", "b"}
