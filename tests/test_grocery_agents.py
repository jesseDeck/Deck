from __future__ import annotations

from pathlib import Path

from deck_broker_agents.grocery_agents import GroceryAgentManager


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

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run


def test_bootstrap_many_creates_three_defaults(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = GroceryAgentManager(client, registry_path=tmp_path / "registry.json")

    registry = manager.bootstrap_many()

    assert sorted(registry) == ["loblaw", "metro", "sobeys"]
    assert len(client.created_sources) == 3
    assert len(client.created_agents) == 3
    assert len(client.created_tasks) == 3


def test_run_profile_extraction_builds_expected_input(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = GroceryAgentManager(client, registry_path=tmp_path / "registry.json")
    manager.bootstrap_many(["loblaw"])

    run = manager.run_profile_extraction(
        grocery_chain="loblaw",
        credential_id="cred_1",
        customer_reference="CUST-100",
        include_order_history=False,
        max_orders=30,
        include_saved_addresses=False,
    )

    assert run["credential_id"] == "cred_1"
    assert run["task_input"]["customer_reference"] == "CUST-100"
    assert run["task_input"]["include_order_history"] is False
    assert run["task_input"]["max_orders"] == 30
    assert run["task_input"]["include_saved_addresses"] is False
