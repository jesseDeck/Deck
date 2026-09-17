"""Thin client for OpenRouter's public catalog API.

Only unauthenticated, public endpoints are used:

- ``GET /api/v1/models`` -- the full model catalog.
- ``GET /api/v1/models/{author}/{slug}/endpoints`` -- per-provider pricing
  and uptime for one model.

OpenRouter does not publish a historical price-change or downtime log through
this API (that view lives behind login at openrouter.ai/workspaces). This
client only ever sees the *current* state of the catalog; building history is
the job of ``snapshot_job.py``, which calls this client repeatedly over time
and appends what it sees to local storage.

The exact endpoint-object schema isn't guaranteed by OpenRouter's public docs
to have stable field names for every attribute (in particular uptime), so the
parsing helpers here are deliberately defensive: they try several known key
spellings and fall back to ``None`` rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

_PRICE_KEYS = {
    "prompt": ["prompt"],
    "completion": ["completion"],
}
_UPTIME_KEYS = ["uptime_last_30m", "uptime_30m", "uptime", "uptime_pct", "uptime_percentage"]
_PROVIDER_NAME_KEYS = ["provider_name", "tag", "name"]


class OpenRouterAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"OpenRouter API error {status_code}: {message}")
        self.status_code = status_code


@dataclass
class ProviderEndpoint:
    """Normalized view of one provider's offering of one model."""

    provider: str
    prompt_price: float | None
    completion_price: float | None
    uptime_pct: float | None
    raw: dict[str, Any]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def parse_endpoint(raw: dict[str, Any]) -> ProviderEndpoint:
    pricing = raw.get("pricing") or {}
    provider = _first_present(raw, _PROVIDER_NAME_KEYS) or "unknown"
    return ProviderEndpoint(
        provider=str(provider),
        prompt_price=_to_float(_first_present(pricing, _PRICE_KEYS["prompt"])),
        completion_price=_to_float(_first_present(pricing, _PRICE_KEYS["completion"])),
        uptime_pct=_to_float(_first_present(raw, _UPTIME_KEYS)),
        raw=raw,
    )


class OpenRouterClient:
    """Minimal wrapper around OpenRouter's public model catalog endpoints."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._session = requests.Session()

    def _get(self, path: str) -> dict[str, Any]:
        response = self._session.get(f"{self.base_url}{path}", timeout=self.timeout_seconds)
        if response.status_code >= 400:
            raise OpenRouterAPIError(response.status_code, response.text)
        return response.json()

    def list_models(self) -> list[dict[str, Any]]:
        """Return the raw model catalog (each item has an ``id`` like ``openai/gpt-4o``)."""
        payload = self._get("/models")
        return payload.get("data", [])

    def list_endpoints(self, model: str) -> list[ProviderEndpoint]:
        """Return normalized per-provider pricing/uptime for one model.

        ``model`` is the canonical ``author/slug`` id, e.g. ``openai/gpt-4o``.
        """
        author, _, slug = model.partition("/")
        if not slug:
            raise ValueError(f"model must be in 'author/slug' form, got {model!r}")
        payload = self._get(f"/models/{author}/{slug}/endpoints")
        data = payload.get("data", payload)
        endpoints = data.get("endpoints", []) if isinstance(data, dict) else []
        return [parse_endpoint(item) for item in endpoints]

    def cheapest_endpoint(self, model: str) -> ProviderEndpoint | None:
        endpoints = [e for e in self.list_endpoints(model) if e.prompt_price is not None]
        if not endpoints:
            return None
        return min(endpoints, key=lambda e: (e.prompt_price or 0, e.completion_price or 0))
