"""Orchestration for a Deck agent that extracts YouTube watch history."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .deck_client import DeckClient

DEFAULT_YOUTUBE_REGISTRY_PATH = Path(".deck") / "youtube_history_agent.json"
DEFAULT_YOUTUBE_SOURCE_URL = "https://www.youtube.com/"


@dataclass(frozen=True)
class YouTubeAgentRecord:
    """Stored Deck resource identifiers for the YouTube history workflow."""

    source_id: str
    source_url: str
    agent_id: str
    task_id: str


def youtube_task_input_schema() -> dict[str, Any]:
    """Schema for requesting a bounded watch-history extraction window."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "start_date": {
                "type": "string",
                "format": "date",
                "description": "Start date in YYYY-MM-DD, inclusive.",
            },
            "end_date": {
                "type": "string",
                "format": "date",
                "description": "End date in YYYY-MM-DD, inclusive.",
            },
            "max_items": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 200,
                "description": "Maximum number of watched videos to return.",
            },
        },
        "required": ["start_date", "end_date"],
    }


def youtube_task_output_schema() -> dict[str, Any]:
    """Schema for normalized YouTube watch history results."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
            "retrieved_at": {"type": "string", "format": "date-time"},
            "total_videos": {"type": "integer"},
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "watched_at": {"type": ["string", "null"], "format": "date-time"},
                        "title": {"type": "string"},
                        "channel_name": {"type": ["string", "null"]},
                        "video_url": {"type": ["string", "null"]},
                        "duration_text": {"type": ["string", "null"]},
                    },
                    "required": ["title"],
                },
            },
        },
        "required": ["start_date", "end_date", "retrieved_at", "entries"],
    }


class YouTubeHistoryAgentManager:
    """Provision and execute Deck tasks for YouTube watch history."""

    def __init__(self, client: DeckClient, registry_path: str | Path = DEFAULT_YOUTUBE_REGISTRY_PATH) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> YouTubeAgentRecord | None:
        if not self.registry_path.exists():
            return None
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return YouTubeAgentRecord(**raw)

    def save_registry(self, record: YouTubeAgentRecord) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(vars(record), handle, indent=2, sort_keys=True)

    def bootstrap(self, *, source_url: str = DEFAULT_YOUTUBE_SOURCE_URL) -> YouTubeAgentRecord:
        source = self.client.create_source(
            name="YouTube",
            website_url=source_url,
        )
        agent = self.client.create_agent(
            name="YouTube Viewing History Extractor",
            description=(
                "Sign in to YouTube and extract the authenticated user's watch history "
                "for a requested date range."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Extract YouTube Viewing History",
            prompt=self._history_prompt(),
            input_schema=youtube_task_input_schema(),
            output_schema=youtube_task_output_schema(),
        )
        record = YouTubeAgentRecord(
            source_id=source["id"],
            source_url=source_url,
            agent_id=agent["id"],
            task_id=task["id"],
        )
        self.save_registry(record)
        return record

    def create_user_credential(
        self,
        *,
        external_id: str,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        record = self.load_registry()
        if record is None:
            raise ValueError("YouTube agent is not bootstrapped yet. Run youtube-bootstrap first.")
        return self.client.create_credential(
            source_id=record.source_id,
            external_id=external_id,
            username=username,
            password=password,
        )

    def run_history_extraction(
        self,
        *,
        credential_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int = 7,
        max_items: int = 200,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        record = self.load_registry()
        if record is None:
            raise ValueError("YouTube agent is not bootstrapped yet. Run youtube-bootstrap first.")
        if days < 1:
            raise ValueError("days must be >= 1")
        if max_items < 1:
            raise ValueError("max_items must be >= 1")

        resolved_end = date.fromisoformat(end_date) if end_date else date.today()
        resolved_start = (
            date.fromisoformat(start_date)
            if start_date
            else resolved_end - timedelta(days=(days - 1))
        )
        if resolved_start > resolved_end:
            raise ValueError("start_date must be on or before end_date")

        task_input = {
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "max_items": max_items,
        }
        return self.client.run_task(
            task_id=record.task_id,
            credential_id=credential_id,
            task_input=task_input,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )

    def wait_for_terminal_status(
        self,
        task_run_id: str,
        *,
        poll_seconds: int = 5,
        timeout_seconds: int = 600,
    ) -> dict[str, Any]:
        terminal_statuses = {"completed", "failed", "canceled", "interaction_required"}
        start = time.time()
        while True:
            current = self.client.get_task_run(task_run_id=task_run_id)
            if current.get("status") in terminal_statuses:
                return current
            if (time.time() - start) > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for task run {task_run_id}")
            time.sleep(poll_seconds)

    @staticmethod
    def _history_prompt() -> str:
        return (
            "Authenticate to YouTube using the provided account credential and navigate to watch "
            "history. Extract watched videos between start_date and end_date (inclusive), newest "
            "first, up to max_items. For each entry return title, channel_name, video_url, "
            "duration_text if visible, and watched_at when available. Do not fabricate missing "
            "fields; return null when data is not visible."
        )
