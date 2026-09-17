"""Poll OpenRouter for the models you're tracking and record what it reports.

This is how price and uptime *history* accumulates locally: run
``take_snapshot`` periodically (via the web server's background loop, a cron
job, or a one-shot CLI invocation) and each call appends one price snapshot
and one uptime snapshot per (tracked model, provider) it can see right now.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .models import PriceSnapshot, UptimeSnapshot
from .openrouter_client import OpenRouterClient
from .storage import Store

logger = logging.getLogger(__name__)


def take_snapshot(store: Store, client: OpenRouterClient) -> dict[str, int]:
    """Fetch current endpoints for every tracked model and store a snapshot.

    Returns a small summary dict (models attempted / endpoints recorded /
    models that failed) rather than raising, so a background polling loop
    can keep going past a single model's API error.
    """
    now = datetime.now(timezone.utc).isoformat()
    tracked = store.tracked_models.all()

    endpoints_recorded = 0
    failed_models: list[str] = []

    for tracked_model in tracked:
        try:
            endpoints = client.list_endpoints(tracked_model.model)
        except Exception as exc:  # noqa: BLE001 - keep polling other models
            logger.warning("Failed to fetch endpoints for %s: %s", tracked_model.model, exc)
            failed_models.append(tracked_model.model)
            continue

        for endpoint in endpoints:
            if endpoint.prompt_price is not None:
                store.price_snapshots.append(
                    PriceSnapshot(
                        model=tracked_model.model,
                        provider=endpoint.provider,
                        prompt_price=endpoint.prompt_price,
                        completion_price=endpoint.completion_price or 0.0,
                        timestamp=now,
                        source="live",
                    )
                )
            store.uptime_snapshots.append(
                UptimeSnapshot(
                    model=tracked_model.model,
                    provider=endpoint.provider,
                    uptime_pct=endpoint.uptime_pct,
                    timestamp=now,
                )
            )
            endpoints_recorded += 1

    return {
        "models_attempted": len(tracked),
        "endpoints_recorded": endpoints_recorded,
        "models_failed": len(failed_models),
    }
