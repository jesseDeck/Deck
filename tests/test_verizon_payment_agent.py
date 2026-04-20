from __future__ import annotations

from pathlib import Path

import pytest

from deck_broker_agents.verizon_payment_agent import VerizonPaymentAgentManager


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
        cred = {"id": self._id("cred"), **kwargs}
        self.created_credentials.append(cred)
        return cred

    def run_task(self, **kwargs):
        run = {"id": self._id("trun"), **kwargs}
        self.runs.append(run)
        return run


def test_bootstrap_creates_verizon_resources(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = VerizonPaymentAgentManager(client, registry_path=tmp_path / "verizon.json")

    record = manager.bootstrap()

    assert record.source_url == "https://www.verizon.com/"
    assert len(client.created_sources) == 1
    assert len(client.created_agents) == 1
    assert len(client.created_tasks) == 1
    assert client.created_tasks[0]["name"] == "Switch Default Card on Verizon Account"


def test_run_payment_switch_builds_expected_input(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = VerizonPaymentAgentManager(client, registry_path=tmp_path / "verizon.json")
    manager.bootstrap()

    run = manager.run_payment_method_switch(
        credential_id="cred_123",
        target_card_last4="4242",
        target_card_label="Personal Visa",
        billing_zip="10001",
        account_nickname="Family Plan",
        confirm_switch=True,
    )

    assert run["credential_id"] == "cred_123"
    assert run["task_input"]["target_card_last4"] == "4242"
    assert run["task_input"]["target_card_label"] == "Personal Visa"
    assert run["task_input"]["billing_zip"] == "10001"
    assert run["task_input"]["account_nickname"] == "Family Plan"
    assert run["task_input"]["confirm_switch"] is True


def test_run_payment_switch_requires_confirm_flag(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = VerizonPaymentAgentManager(client, registry_path=tmp_path / "verizon.json")
    manager.bootstrap()

    with pytest.raises(ValueError, match="confirm_switch must be true"):
        manager.run_payment_method_switch(
            credential_id="cred_123",
            target_card_last4="4242",
            confirm_switch=False,
        )


def test_run_payment_switch_requires_last4_validation(tmp_path: Path) -> None:
    client = FakeDeckClient()
    manager = VerizonPaymentAgentManager(client, registry_path=tmp_path / "verizon.json")
    manager.bootstrap()

    with pytest.raises(ValueError, match="target_card_last4 must be exactly 4 digits"):
        manager.run_payment_method_switch(
            credential_id="cred_123",
            target_card_last4="42A2",
            confirm_switch=True,
        )
