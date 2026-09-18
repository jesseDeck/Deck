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
from .openrouter_client import OpenRouterClient, parse_catalog_pricing
from .storage import Store

logger = logging.getLogger(__name__)

CATALOG_PROVIDER_LABEL = "openrouter (catalog)"


def take_snapshot(store: Store, client: OpenRouterClient) -> dict[str, int]:
    """Fetch current endpoints for every tracked model, plus one catalog-wide
    pricing snapshot, and store the result.

    Returns a small summary dict rather than raising, so a background polling
    loop can keep going past a single model's API error.
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

    catalog_result = snapshot_catalog(store, client, timestamp=now)

    return {
        "models_attempted": len(tracked),
        "endpoints_recorded": endpoints_recorded,
        "models_failed": len(failed_models),
        "catalog_models_recorded": catalog_result["models_recorded"],
    }


def snapshot_catalog(
    store: Store,
    client: OpenRouterClient,
    *,
    timestamp: str | None = None,
    min_interval_minutes: float = 60.0,
) -> dict[str, int]:
    """Record one broad, catalog-wide price snapshot covering every model.

    Uses ``list_models()`` (a single API call) rather than drilling into each
    model's per-provider endpoints, so this stays cheap even across
    OpenRouter's full catalog. This is what makes "any available model" and
    unnamed substitute-model comparisons possible without one API call per
    candidate model.

    A whole-catalog snapshot is hundreds of rows, so if the background poller
    runs every few minutes this skips re-snapshotting within
    ``min_interval_minutes`` of the last one, to avoid ballooning local
    storage with near-duplicate data.
    """
    now = timestamp or datetime.now(timezone.utc).isoformat()
    existing = store.price_snapshots.all()
    catalog_timestamps = [s.timestamp for s in existing if s.provider == CATALOG_PROVIDER_LABEL]
    if catalog_timestamps:
        latest = max(catalog_timestamps)
        try:
            age_minutes = (datetime.fromisoformat(now) - datetime.fromisoformat(latest)).total_seconds() / 60.0
            if 0 <= age_minutes < min_interval_minutes:
                return {"models_recorded": 0, "skipped_recent": True}
        except ValueError:
            pass

    try:
        models = client.list_models()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch model catalog: %s", exc)
        return {"models_recorded": 0}

    recorded = 0
    for raw_model in models:
        model_id = raw_model.get("id")
        if not model_id:
            continue
        prompt_price, completion_price = parse_catalog_pricing(raw_model)
        if prompt_price is None:
            continue
        store.price_snapshots.append(
            PriceSnapshot(
                model=model_id,
                provider=CATALOG_PROVIDER_LABEL,
                prompt_price=prompt_price,
                completion_price=completion_price or 0.0,
                timestamp=now,
                source="live",
            )
        )
        recorded += 1
    return {"models_recorded": recorded}
