from __future__ import annotations

from datetime import date
from pathlib import Path

import deck_broker_agents.youtube_history_agent as youtube_module
from deck_broker_agents.youtube_history_agent import YouTubeHistoryAgentManager


class FakeDeckClient:
    def __init__(self) -> None:
        self.created_sources = []
        self.created_agents = []
        self.created_tasks = []
        self.runs = []
        self._counter = 0

    def _id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def create_source(self, *, name: str, website_url: str):
        source = {"id": self._id("src"), "name": name, "website": {"url": website_url}}
        self.created_sources.append(source)
        return source

    def create_agent(self, *, name: str, description: str):
        agent = {"id": self._id("agt"), "name": name, "description": description}
        self.created_agents.append(agent)
        return agent

    def create_task(self, **kwargs):
        task = {"id": self._id("task"), **kwargs}
        self.created_tasks.append(task)
        return task

    def create_credential(self, **kwargs):
        return {"id": self._id("cred"), **kwargs}

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run


def test_bootstrap_creates_youtube_resources(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = YouTubeHistoryAgentManager(client, registry_path=tmp_path / "youtube.json")

    record = manager.bootstrap()

    assert record.source_url == "https://www.youtube.com/"
    assert len(client.created_sources) == 1
    assert len(client.created_agents) == 1
    assert len(client.created_tasks) == 1


def test_run_history_extraction_defaults_to_last_week(tmp_path: Path, monkeypatch) -> None:
    client = FakeDeckClient()
    manager = YouTubeHistoryAgentManager(client, registry_path=tmp_path / "youtube.json")
    manager.bootstrap()

    class _FixedDate(date):
        @classmethod
        def today(cls) -> "_FixedDate":
            return cls(2026, 4, 20)

    monkeypatch.setattr(youtube_module, "date", _FixedDate)

    run = manager.run_history_extraction(credential_id="cred_1")

    assert run["credential_id"] == "cred_1"
    assert run["task_input"]["start_date"] == "2026-04-14"
    assert run["task_input"]["end_date"] == "2026-04-20"
    assert run["task_input"]["max_items"] == 200


def test_run_history_extraction_rejects_inverted_dates(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = YouTubeHistoryAgentManager(client, registry_path=tmp_path / "youtube.json")
    manager.bootstrap()

    try:
        manager.run_history_extraction(
            credential_id="cred_1",
            start_date="2026-04-21",
            end_date="2026-04-20",
        )
        assert False, "Expected ValueError for start_date > end_date"
    except ValueError as exc:
        assert "start_date" in str(exc)
