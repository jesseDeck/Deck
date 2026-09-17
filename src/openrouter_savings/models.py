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
class TrackedModel:
    """A model you've asked this tool to keep polling OpenRouter for."""

    model: str
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "label": self.label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackedModel":
        return cls(model=data["model"], label=data.get("label", ""))
