from __future__ import annotations

from pathlib import Path

import pytest

from deck_broker_agents.claims_agents import ClaimsAgentManager
from deck_broker_agents.claims_models import CLAIMS_SOURCES, claims_task_output_schema


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

    def create_credential(self, **kwargs):
        credential = {"id": self._id("cred"), "auth_method": "username_password", **kwargs}
        self.created_credentials.append(credential)
        return credential

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run


def test_claims_bootstrap_defaults_to_all_ten_portals(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = ClaimsAgentManager(client, registry_path=tmp_path / "claims_registry.json")

    registry = manager.bootstrap_many()

    assert sorted(registry) == sorted(CLAIMS_SOURCES)
    assert len(CLAIMS_SOURCES) == 10
    assert len(client.created_agents) == 10
    assert all(task["storage"]["enabled"] for task in client.created_tasks)


def test_claims_bootstrap_is_idempotent(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = ClaimsAgentManager(client, registry_path=tmp_path / "claims_registry.json")

    manager.bootstrap_many(["cigna", "aetna"])
    manager.bootstrap_many(["cigna", "aetna", "uhc"])

    assert len(client.created_agents) == 3


def test_claims_bootstrap_override_reprovisions_source(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = ClaimsAgentManager(client, registry_path=tmp_path / "claims_registry.json")
    manager.bootstrap_many(["mychart"])

    registry = manager.bootstrap_many(
        ["mychart"],
        source_url_overrides={"mychart": "https://mychart.example-health.org/"},
    )

    assert registry["mychart"].source_url == "https://mychart.example-health.org/"
    assert len(client.created_agents) == 2


def test_claims_output_requires_patient_responsibility() -> None:
    item = claims_task_output_schema()["properties"]["claims"]["items"]

    for field in (
        "claim_id",
        "status",
        "claim_type",
        "plan_name",
        "provider_name",
        "service_date",
        "billed_amount",
        "plan_paid_amount",
        "patient_responsibility",
    ):
        assert field in item["required"]


def test_provider_portal_prompt_mentions_statements(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = ClaimsAgentManager(client, registry_path=tmp_path / "claims_registry.json")

    manager.bootstrap_many(["cigna", "eclinicalworks"])

    cigna_prompt, ecw_prompt = (task["prompt"] for task in client.created_tasks)
    assert "member portal" in cigna_prompt
    assert "statement" in ecw_prompt
    assert "patient/member responsibility" in ecw_prompt


def test_claims_run_builds_input(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = ClaimsAgentManager(client, registry_path=tmp_path / "claims_registry.json")
    manager.bootstrap_many(["uhc"])

    run = manager.run_claims_extraction(
        portal="UHC",
        credential_id="cred_abc",
        service_date_from="2026-01-01",
        member_name="Jane Doe",
        download_eobs=False,
    )

    assert run["credential_id"] == "cred_abc"
    assert run["task_input"] == {
        "max_claims": 200,
        "download_eobs": False,
        "service_date_from": "2026-01-01",
        "member_name": "Jane Doe",
    }


def test_unknown_portal_rejected(tmp_path: Path) -> None:
    manager = ClaimsAgentManager(FakeDeckClient(), registry_path=tmp_path / "claims_registry.json")

    with pytest.raises(ValueError, match="Unknown portal"):
        manager.bootstrap_many(["kaiser"])


def test_storage_extraction_schema_omits_additional_properties() -> None:
    # Deck rejects additionalProperties inside storage.extraction_schema (422 invalid_field_value).
    from deck_broker_agents.claims_models import claims_storage_extraction_schema

    assert "additionalProperties" not in claims_storage_extraction_schema()
