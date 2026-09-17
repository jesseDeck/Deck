"""Expand a ModelProfile (a usage *rate*) into synthetic monthly usage entries.

Rather than log every request, a profile describes how long you've used a
model and roughly how much per month. This expands that into one
``UsageEntry`` per calendar month in the usage window, timestamped at each
month's start, so it flows through the exact same savings math
(``savings.compute_savings``) as manually-logged usage -- including being
time-aware against any price history you've backfilled for that period.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import ModelProfile, UsageEntry


def _parse_date(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _month_starts(start: datetime, end: datetime) -> list[datetime]:
    """First-of-month timestamps from ``start``'s month through ``end``'s month, inclusive.

    Always returns at least one month, even if start and end fall in the same
    month or end precedes start.
    """
    months: list[datetime] = []
    year, month = start.year, start.month
    end_year, end_month = end.year, end.month
    while (year, month) <= (end_year, end_month):
        months.append(datetime(year, month, 1, tzinfo=start.tzinfo))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months or [datetime(start.year, start.month, 1, tzinfo=start.tzinfo)]


def profile_to_usage_entries(profile: ModelProfile, *, now: datetime | None = None) -> list[UsageEntry]:
    """Expand one profile into one synthetic ``UsageEntry`` per calendar month.

    Each month gets the profile's full monthly token/cost rate -- partial
    start/end months are counted as whole months, a deliberate simplification
    since this is inherently a rough estimate rather than a precise log.
    """
    start = _parse_date(profile.used_since)
    end = _parse_date(profile.used_until) if profile.used_until else (now or datetime.now(timezone.utc))

    entries: list[UsageEntry] = []
    for month_start in _month_starts(start, end):
        entries.append(
            UsageEntry(
                model=profile.model,
                provider_used=profile.provider_used or "profile",
                timestamp=month_start.isoformat(),
                prompt_tokens=int(profile.monthly_prompt_tokens),
                completion_tokens=int(profile.monthly_completion_tokens),
                actual_cost=profile.monthly_cost,
                unit_prompt_price=profile.unit_prompt_price,
                unit_completion_price=profile.unit_completion_price,
                acceptable_models=profile.acceptable_models,
                any_model_acceptable=profile.any_model_acceptable,
                notes=f"profile:{profile.id}",
            )
        )
    return entries


def profiles_to_usage_entries(profiles: list[ModelProfile], *, now: datetime | None = None) -> list[UsageEntry]:
    entries: list[UsageEntry] = []
    for profile in profiles:
        entries.extend(profile_to_usage_entries(profile, now=now))
    return entries
