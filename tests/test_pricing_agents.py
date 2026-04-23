from __future__ import annotations

from pathlib import Path

from deck_broker_agents.pricing_agents import PricingAgentManager


class FakeDeckClient:
    def __init__(self) -> None:
        self.created_sources = []
        self.created_agents = []
        self.created_tasks = []
        self.created_credentials = []
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

    def create_no_auth_credential(self, *, source_id: str, external_id: str):
        credential = {
            "id": self._id("cred"),
            "source_id": source_id,
            "external_id": external_id,
            "auth_method": "none",
        }
        self.created_credentials.append(credential)
        return credential

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run


def test_pricing_bootstrap_defaults_to_ferguson(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = PricingAgentManager(client, registry_path=tmp_path / "pricing_registry.json")

    registry = manager.bootstrap_many()

    assert sorted(registry) == ["ferguson"]
    assert len(client.created_sources) == 1
    assert len(client.created_agents) == 1
    assert len(client.created_tasks) == 1
    assert client.created_sources[0]["website"]["url"] == "https://www.ferguson.com/"


def test_pricing_run_defaults_to_faucets_and_sinks(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = PricingAgentManager(client, registry_path=tmp_path / "pricing_registry.json")
    manager.bootstrap_many(["ferguson"])

    run = manager.run_pricing_extraction(
        catalog="ferguson",
        credential_id=None,
        search_terms=["kitchen"],
        include_out_of_stock=True,
    )

    assert run["task_input"]["categories"] == ["faucets", "sinks"]
    assert run["task_input"]["search_terms"] == ["kitchen"]
    assert run["task_input"]["include_out_of_stock"] is True


def test_create_public_credential_uses_no_auth(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = PricingAgentManager(client, registry_path=tmp_path / "pricing_registry.json")
    manager.bootstrap_many(["ferguson"])

    credential = manager.create_public_credential(catalog="ferguson", external_id="user_123")

    assert credential["auth_method"] == "none"
    assert client.created_credentials[0]["external_id"] == "user_123"
