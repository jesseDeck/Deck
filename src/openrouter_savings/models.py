"""Domain models for tracked usage, pricing, and uptime data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class UsageEntry:
    """A single real-world request (or batch of requests) you actually paid for.

    ``model`` is the OpenRouter canonical slug (``author/slug``, e.g.
    ``openai/gpt-4o``) so it can be matched against OpenRouter's catalog even
    though you called the provider directly rather than through OpenRouter.
    """

    model: str
    provider_used: str
    timestamp: str  # ISO 8601
    prompt_tokens: int = 0
    completion_tokens: int = 0
    request_count: int = 1
    unit_prompt_price: float | None = None  # $ per token, if actual_cost not given
    unit_completion_price: float | None = None
    actual_cost: float | None = None  # $ actually paid; computed from unit prices if omitted
    notes: str = ""
    id: str = field(default_factory=new_id)
    # Which models OpenRouter would have been allowed to route this usage to instead of
    # ``model``. Empty + any_model_acceptable=False (the default) means "only compare
    # providers of this same model" (the original behavior). ``model`` itself is always
    # implicitly acceptable, so it doesn't need to be repeated in this list.
    acceptable_models: list[str] = field(default_factory=list)
    any_model_acceptable: bool = False  # True = compare against every model we have pricing for

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "provider_used": self.provider_used,
            "timestamp": self.timestamp,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "request_count": self.request_count,
            "unit_prompt_price": self.unit_prompt_price,
            "unit_completion_price": self.unit_completion_price,
            "actual_cost": self.actual_cost,
            "notes": self.notes,
            "acceptable_models": self.acceptable_models,
            "any_model_acceptable": self.any_model_acceptable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageEntry":
        return cls(
            id=data.get("id") or new_id(),
            model=data["model"],
            provider_used=data["provider_used"],
            timestamp=data["timestamp"],
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            request_count=int(data.get("request_count", 1)),
            unit_prompt_price=data.get("unit_prompt_price"),
            unit_completion_price=data.get("unit_completion_price"),
            actual_cost=data.get("actual_cost"),
            notes=data.get("notes", ""),
            acceptable_models=list(data.get("acceptable_models") or []),
            any_model_acceptable=bool(data.get("any_model_acceptable", False)),
        )


@dataclass
class PriceSnapshot:
    """Observed prompt/completion pricing for one provider serving one model."""

    model: str
    provider: str
    prompt_price: float  # $ per token
    completion_price: float  # $ per token
    timestamp: str  # ISO 8601, when this price was observed/effective
    source: str = "live"  # "live" (polled from OpenRouter) or "import" (backfilled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "prompt_price": self.prompt_price,
            "completion_price": self.completion_price,
            "timestamp": self.timestamp,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriceSnapshot":
        return cls(
            model=data["model"],
            provider=data["provider"],
            prompt_price=float(data["prompt_price"]),
            completion_price=float(data["completion_price"]),
            timestamp=data["timestamp"],
            source=data.get("source", "live"),
        )


@dataclass
class UptimeSnapshot:
    """Observed uptime percentage for one provider serving one model."""

    model: str
    provider: str
    uptime_pct: float | None  # 0-100, None if OpenRouter did not report it
    timestamp: str  # ISO 8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "uptime_pct": self.uptime_pct,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UptimeSnapshot":
        return cls(
            model=data["model"],
            provider=data["provider"],
            uptime_pct=data.get("uptime_pct"),
            timestamp=data["timestamp"],
        )


@dataclass
class DowntimeIncident:
    """A discrete outage window backfilled from an external source.

    Unlike ``UptimeSnapshot`` (a point-in-time percentage this tool polled
    itself), this represents a known start/end outage window imported from
    elsewhere -- e.g. a status-monitoring site's incident history -- so it can
    cover time before you started tracking.
    """

    model: str
    provider: str
    start: str  # ISO 8601
    end: str  # ISO 8601
    source: str = "import"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DowntimeIncident":
        return cls(
            model=data["model"],
            provider=data["provider"],
            start=data["start"],
            end=data["end"],
            source=data.get("source", "import"),
            notes=data.get("notes", ""),
        )


@dataclass
class TrackedModel:
    """A model you've asked this tool to keep polling OpenRouter for."""

    model: str
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "label": self.label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackedModel":
        return cls(model=data["model"], label=data.get("label", ""))


@dataclass
class ModelProfile:
    """A model you use regularly, described as a usage *rate* rather than a log.

    Instead of logging every request, you describe how long you've been using
    ``model`` and roughly how much per month, plus which other models
    OpenRouter would have been allowed to substitute in. ``profiles.py``
    expands this into one synthetic monthly ``UsageEntry`` per calendar month
    in the usage window, which then flows through the same savings math as
    manually-logged usage.
    """

    model: str
    used_since: str  # ISO 8601 date; start of the usage window
    id: str = field(default_factory=new_id)
    label: str = ""
    provider_used: str = ""
    used_until: str | None = None  # None means "ongoing" (through today)
    monthly_prompt_tokens: float = 0
    monthly_completion_tokens: float = 0
    monthly_cost: float | None = None  # $ actually paid per month; derived from unit prices if omitted
    unit_prompt_price: float | None = None
    unit_completion_price: float | None = None
    acceptable_models: list[str] = field(default_factory=list)
    any_model_acceptable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "label": self.label,
            "provider_used": self.provider_used,
            "used_since": self.used_since,
            "used_until": self.used_until,
            "monthly_prompt_tokens": self.monthly_prompt_tokens,
            "monthly_completion_tokens": self.monthly_completion_tokens,
            "monthly_cost": self.monthly_cost,
            "unit_prompt_price": self.unit_prompt_price,
            "unit_completion_price": self.unit_completion_price,
            "acceptable_models": self.acceptable_models,
            "any_model_acceptable": self.any_model_acceptable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelProfile":
        return cls(
            id=data.get("id") or new_id(),
            model=data["model"],
            label=data.get("label", ""),
            provider_used=data.get("provider_used", ""),
            used_since=data["used_since"],
            used_until=data.get("used_until"),
            monthly_prompt_tokens=float(data.get("monthly_prompt_tokens", 0)),
            monthly_completion_tokens=float(data.get("monthly_completion_tokens", 0)),
            monthly_cost=data.get("monthly_cost"),
            unit_prompt_price=data.get("unit_prompt_price"),
            unit_completion_price=data.get("unit_completion_price"),
            acceptable_models=list(data.get("acceptable_models") or []),
            any_model_acceptable=bool(data.get("any_model_acceptable", False)),
        )
