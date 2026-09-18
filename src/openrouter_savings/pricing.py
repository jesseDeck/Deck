"""Pure cost-calculation helpers (no I/O, easy to unit test)."""

from __future__ import annotations

from .models import PriceSnapshot, UsageEntry


def actual_cost(entry: UsageEntry) -> float:
    """What you actually paid for this usage entry.

    Uses ``actual_cost`` directly if it was given; otherwise derives it from
    token counts and unit prices.
    """
    if entry.actual_cost is not None:
        return entry.actual_cost
    prompt_price = entry.unit_prompt_price or 0.0
    completion_price = entry.unit_completion_price or 0.0
    return entry.prompt_tokens * prompt_price + entry.completion_tokens * completion_price


def cost_at_snapshot(entry: UsageEntry, snapshot: PriceSnapshot) -> float:
    """What this usage would have cost at a given provider's observed price."""
    return entry.prompt_tokens * snapshot.prompt_price + entry.completion_tokens * snapshot.completion_price


def cheapest_snapshot_at_or_before(
    snapshots: list[PriceSnapshot],
    model: str,
    at_or_before: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    acceptable_models: list[str] | None = None,
    any_model_acceptable: bool = False,
) -> tuple[PriceSnapshot | None, bool]:
    """Pick the (model, provider) that would have been cheapest for this usage.

    By default only ``model``'s own providers are considered (OpenRouter
    routing across providers of the same model). Pass ``acceptable_models``
    to also consider specific substitute models -- ``model`` itself is always
    implicitly included -- or ``any_model_acceptable=True`` to consider every
    model any snapshot has pricing for (full auto-route).

    For each (model, provider) pair we know a price for, use its most recent
    snapshot at or before ``at_or_before``; if no such snapshot exists (all of
    its observations are later than the usage), fall back to its earliest
    known snapshot instead, since it's the closest estimate we have.
    Candidates are then ranked by what this specific
    ``prompt_tokens``/``completion_tokens`` mix would actually have cost at
    their snapshot price, not a generic per-token average, since prompt-heavy
    and completion-heavy workloads can favor different cheapest options.

    Returns ``(cheapest, is_estimated)`` where ``is_estimated`` is True when
    the chosen snapshot didn't actually precede the usage timestamp (i.e. we
    only had pricing from after the fact to go on).
    """
    wanted_models = None if any_model_acceptable else {model, *(acceptable_models or [])}

    by_key: dict[tuple[str, str], list[PriceSnapshot]] = {}
    for snap in snapshots:
        if wanted_models is not None and snap.model not in wanted_models:
            continue
        by_key.setdefault((snap.model, snap.provider), []).append(snap)

    best: PriceSnapshot | None = None
    best_is_estimated = False
    best_cost = float("inf")
    for candidate_snaps in by_key.values():
        candidate_snaps.sort(key=lambda s: s.timestamp)
        chosen = None
        estimated = False
        for snap in candidate_snaps:
            if snap.timestamp <= at_or_before:
                chosen = snap  # keep advancing to the latest one still <= cutoff
            else:
                break
        if chosen is None:
            chosen = candidate_snaps[0]
            estimated = True

        candidate_cost = prompt_tokens * chosen.prompt_price + completion_tokens * chosen.completion_price
        if candidate_cost < best_cost:
            best = chosen
            best_is_estimated = estimated
            best_cost = candidate_cost

    return best, best_is_estimated
