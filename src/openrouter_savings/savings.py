"""Aggregate savings calculation: actual spend vs. best OpenRouter routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import PriceSnapshot, UsageEntry
from .openrouter_client import OpenRouterClient
from .pricing import actual_cost, cheapest_snapshot_at_or_before


@dataclass
class EntryResult:
    entry: UsageEntry
    actual: float
    best_openrouter_cost: float | None
    best_openrouter_provider: str | None
    savings: float | None  # actual - best_openrouter_cost; None if no price data at all
    is_estimated: bool  # True if we had no price observed at/before this entry's timestamp


@dataclass
class SavingsReport:
    results: list[EntryResult]
    total_actual: float = 0.0
    total_best_openrouter: float = 0.0
    total_savings: float = 0.0
    entries_missing_price_data: int = 0
    by_model: dict[str, dict[str, float]] = field(default_factory=dict)
    by_provider_used: dict[str, dict[str, float]] = field(default_factory=dict)
    timeseries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_actual": round(self.total_actual, 6),
            "total_best_openrouter": round(self.total_best_openrouter, 6),
            "total_savings": round(self.total_savings, 6),
            "savings_pct": (
                round(100 * self.total_savings / self.total_actual, 2) if self.total_actual else 0.0
            ),
            "entries_missing_price_data": self.entries_missing_price_data,
            "by_model": self.by_model,
            "by_provider_used": self.by_provider_used,
            "timeseries": self.timeseries,
            "entries": [
                {
                    "id": r.entry.id,
                    "model": r.entry.model,
                    "provider_used": r.entry.provider_used,
                    "timestamp": r.entry.timestamp,
                    "actual_cost": round(r.actual, 6),
                    "best_openrouter_cost": (
                        round(r.best_openrouter_cost, 6) if r.best_openrouter_cost is not None else None
                    ),
                    "best_openrouter_provider": r.best_openrouter_provider,
                    "savings": round(r.savings, 6) if r.savings is not None else None,
                    "is_estimated": r.is_estimated,
                }
                for r in self.results
            ],
        }


def _bucket_day(timestamp: str) -> str:
    return timestamp[:10] if len(timestamp) >= 10 else timestamp


def compute_savings(
    entries: list[UsageEntry],
    price_snapshots: list[PriceSnapshot],
    *,
    live_client: OpenRouterClient | None = None,
) -> SavingsReport:
    """Compute per-entry and aggregate savings.

    For each entry, the cheapest OpenRouter provider price is resolved from
    locally stored snapshots first (see ``pricing.cheapest_snapshot_at_or_before``).
    If nothing is known locally for that model at all and ``live_client`` is
    given, a live lookup against OpenRouter's current catalog is attempted as
    a last resort (flagged as estimated, since it reflects today's price, not
    the price on the entry's date).
    """
    results: list[EntryResult] = []
    live_cache: dict[str, tuple[str, float, float] | None] = {}
    day_totals: dict[str, dict[str, float]] = {}

    for entry in entries:
        paid = actual_cost(entry)
        best_snapshot, is_estimated = cheapest_snapshot_at_or_before(
            price_snapshots,
            entry.model,
            entry.timestamp,
            prompt_tokens=entry.prompt_tokens,
            completion_tokens=entry.completion_tokens,
        )

        best_cost: float | None = None
        best_provider: str | None = None
        if best_snapshot is not None:
            best_cost = entry.prompt_tokens * best_snapshot.prompt_price + (
                entry.completion_tokens * best_snapshot.completion_price
            )
            best_provider = best_snapshot.provider
        elif live_client is not None:
            if entry.model not in live_cache:
                live_cache[entry.model] = _try_live_cheapest(live_client, entry.model)
            live = live_cache[entry.model]
            if live is not None:
                provider, prompt_price, completion_price = live
                best_cost = entry.prompt_tokens * prompt_price + entry.completion_tokens * completion_price
                best_provider = provider
                is_estimated = True

        savings = (paid - best_cost) if best_cost is not None else None

        results.append(
            EntryResult(
                entry=entry,
                actual=paid,
                best_openrouter_cost=best_cost,
                best_openrouter_provider=best_provider,
                savings=savings,
                is_estimated=is_estimated,
            )
        )

        day = _bucket_day(entry.timestamp)
        bucket = day_totals.setdefault(day, {"actual": 0.0, "best_openrouter": 0.0})
        bucket["actual"] += paid
        bucket["best_openrouter"] += best_cost if best_cost is not None else paid

    report = SavingsReport(results=results)
    for r in results:
        report.total_actual += r.actual
        if r.best_openrouter_cost is not None:
            report.total_best_openrouter += r.best_openrouter_cost
            report.total_savings += r.savings or 0.0
        else:
            report.entries_missing_price_data += 1
            report.total_best_openrouter += r.actual  # no comparison available; count as break-even

        model_bucket = report.by_model.setdefault(
            r.entry.model, {"actual": 0.0, "best_openrouter": 0.0, "savings": 0.0}
        )
        model_bucket["actual"] += r.actual
        model_bucket["best_openrouter"] += r.best_openrouter_cost if r.best_openrouter_cost is not None else r.actual
        model_bucket["savings"] += r.savings or 0.0

        provider_bucket = report.by_provider_used.setdefault(
            r.entry.provider_used, {"actual": 0.0, "best_openrouter": 0.0, "savings": 0.0}
        )
        provider_bucket["actual"] += r.actual
        provider_bucket["best_openrouter"] += (
            r.best_openrouter_cost if r.best_openrouter_cost is not None else r.actual
        )
        provider_bucket["savings"] += r.savings or 0.0

    report.timeseries = [
        {"date": day, "actual": totals["actual"], "best_openrouter": totals["best_openrouter"]}
        for day, totals in sorted(day_totals.items())
    ]
    return report


def _try_live_cheapest(client: OpenRouterClient, model: str) -> tuple[str, float, float] | None:
    try:
        endpoint = client.cheapest_endpoint(model)
    except Exception:
        return None
    if endpoint is None or endpoint.prompt_price is None:
        return None
    return endpoint.provider, endpoint.prompt_price, endpoint.completion_price or 0.0
