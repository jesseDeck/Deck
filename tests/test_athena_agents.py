from __future__ import annotations

from pathlib import Path

import pytest

from deck_broker_agents.athena_agents import AthenaHealthAgentManager


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
        credential = {"id": self._id("cred"), **kwargs}
        self.created_credentials.append(credential)
        return credential

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run


def test_bootstrap_creates_athena_resources(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = AthenaHealthAgentManager(client, registry_path=tmp_path / "athena.json")

    record = manager.bootstrap()

    assert record.source_url == "https://athenanet.athenahealth.com/"
    assert len(client.created_sources) == 1
    assert len(client.created_agents) == 1
    assert len(client.created_tasks) == 1
    assert client.created_tasks[0]["name"] == "Extract Patient Medical Record"


def test_create_credential_supports_source_fields(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = AthenaHealthAgentManager(client, registry_path=tmp_path / "athena.json")
    manager.bootstrap()

    credential = manager.create_user_credential(
        external_id="patient_user_1",
        username="user@example.com",
        password="secret",
        source_fields={"department_id": "77"},
    )

    assert credential["source_fields"] == {"department_id": "77"}
    assert credential["external_id"] == "patient_user_1"


def test_run_medical_record_extraction_builds_expected_input(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = AthenaHealthAgentManager(client, registry_path=tmp_path / "athena.json")
    manager.bootstrap()

    run = manager.run_medical_record_extraction(
        credential_id="cred_1",
        patient_reference="MRN-12345",
        date_from="2025-01-01",
        date_to="2025-12-31",
        include_sections=["Vitals", "labs"],
    )

    assert run["credential_id"] == "cred_1"
    assert run["task_input"]["patient_reference"] == "MRN-12345"
    assert run["task_input"]["date_from"] == "2025-01-01"
    assert run["task_input"]["date_to"] == "2025-12-31"
    assert run["task_input"]["include_sections"] == ["vitals", "labs"]


def test_run_medical_record_extraction_rejects_invalid_sections(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = AthenaHealthAgentManager(client, registry_path=tmp_path / "athena.json")
    manager.bootstrap()

    with pytest.raises(ValueError, match="Invalid include section"):
        manager.run_medical_record_extraction(
            credential_id="cred_1",
            patient_reference="MRN-12345",
            include_sections=["invalid_section"],
        )
