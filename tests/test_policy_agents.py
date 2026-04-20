from __future__ import annotations

from pathlib import Path

from deck_broker_agents.policy_agents import PolicyAgentManager


class FakeDeckClient:
    def __init__(self) -> None:
        self.created_sources = []
        self.created_agents = []
        self.created_tasks = []
        self.runs = []
        self.credentials = []
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

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run

    def create_credential(self, **kwargs):
        credential = {"id": self._id("cred"), **kwargs}
        self.credentials.append(credential)
        return credential


def test_bootstrap_many_creates_three_defaults(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = PolicyAgentManager(client, registry_path=tmp_path / "registry.json")

    registry = manager.bootstrap_many()

    assert sorted(registry) == ["acturis", "open_gi", "ssp"]
    assert len(client.created_sources) == 3
    assert len(client.created_agents) == 3
    assert len(client.created_tasks) == 3


def test_run_policy_extraction_builds_expected_input(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = PolicyAgentManager(client, registry_path=tmp_path / "registry.json")
    manager.bootstrap_many(["acturis"])

    run = manager.run_policy_extraction(
        broker_system="acturis",
        credential_id="cred_1",
        client_reference="CL-100",
        policy_numbers=["P-1", "P-2"],
        include_inactive=True,
        as_of_date="2026-04-01",
    )

    assert run["credential_id"] == "cred_1"
    assert run["task_input"]["client_reference"] == "CL-100"
    assert run["task_input"]["policy_numbers"] == ["P-1", "P-2"]
    assert run["task_input"]["include_inactive"] is True
    assert run["task_input"]["as_of_date"] == "2026-04-01"
