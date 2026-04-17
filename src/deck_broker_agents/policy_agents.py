"""High-level orchestration for broker policy extraction agents."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deck_client import DeckClient
from .models import BROKER_SYSTEMS, storage_extraction_schema, task_input_schema, task_output_schema

DEFAULT_REGISTRY_PATH = Path(".deck") / "broker_agents.json"


@dataclass(frozen=True)
class BrokerAgentRecord:
    """Stored Deck resource IDs for one broker system."""

    broker_system: str
    source_id: str
    source_url: str
    agent_id: str
    task_id: str


class PolicyAgentManager:
    """Manages provisioning and execution of Deck policy extraction tasks."""

    def __init__(self, client: DeckClient, registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> dict[str, BrokerAgentRecord]:
        if not self.registry_path.exists():
            return {}
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {key: BrokerAgentRecord(**value) for key, value in raw.items()}

    def save_registry(self, registry: dict[str, BrokerAgentRecord]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        raw = {key: vars(value) for key, value in registry.items()}
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2, sort_keys=True)

    def bootstrap(
        self,
        broker_system: str,
        *,
        source_url: str | None = None,
    ) -> BrokerAgentRecord:
        key = broker_system.lower().strip()
        if key not in BROKER_SYSTEMS:
            allowed = ", ".join(sorted(BROKER_SYSTEMS))
            raise ValueError(f"Unknown broker_system '{broker_system}'. Expected one of: {allowed}")

        system = BROKER_SYSTEMS[key]
        source = self.client.create_source(
            name=f"{system.display_name} Broker Platform",
            website_url=source_url or system.default_source_url,
        )
        agent = self.client.create_agent(
            name=f"{system.display_name} Policy Data Extractor",
            description=(
                "Extract client policy records and policy documents in a normalized schema "
                f"from {system.display_name}."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Extract Client Policy Data",
            prompt=self._policy_prompt(system.display_name),
            input_schema=task_input_schema(),
            output_schema=task_output_schema(),
            storage={
                "enabled": True,
                "extraction": True,
                "deduplication": True,
                "extraction_schema": storage_extraction_schema(),
            },
        )
        return BrokerAgentRecord(
            broker_system=key,
            source_id=source["id"],
            source_url=(source_url or system.default_source_url),
            agent_id=agent["id"],
            task_id=task["id"],
        )

    def bootstrap_many(
        self,
        broker_systems: list[str] | None = None,
        *,
        source_url_overrides: dict[str, str] | None = None,
    ) -> dict[str, BrokerAgentRecord]:
        systems = broker_systems or sorted(BROKER_SYSTEMS.keys())
        source_url_overrides = source_url_overrides or {}

        registry = self.load_registry()
        for key in systems:
            normalized_key = key.lower().strip()
            record = self.bootstrap(
                normalized_key,
                source_url=source_url_overrides.get(normalized_key),
            )
            registry[normalized_key] = record
        self.save_registry(registry)
        return registry

    def create_user_credential(
        self,
        *,
        broker_system: str,
        external_id: str,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        registry = self.load_registry()
        key = broker_system.lower().strip()
        if key not in registry:
            raise ValueError(
                f"{broker_system} is not bootstrapped yet. Run bootstrap first so source_id is available."
            )
        return self.client.create_credential(
            source_id=registry[key].source_id,
            external_id=external_id,
            username=username,
            password=password,
        )

    def run_policy_extraction(
        self,
        *,
        broker_system: str,
        credential_id: str,
        client_reference: str,
        policy_numbers: list[str] | None = None,
        include_inactive: bool = False,
        as_of_date: str | None = None,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = broker_system.lower().strip()
        registry = self.load_registry()
        if key not in registry:
            raise ValueError(f"{broker_system} is not bootstrapped yet.")

        task_input: dict[str, Any] = {
            "client_reference": client_reference,
            "include_inactive": include_inactive,
        }
        if policy_numbers:
            task_input["policy_numbers"] = policy_numbers
        if as_of_date:
            task_input["as_of_date"] = as_of_date

        return self.client.run_task(
            task_id=registry[key].task_id,
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
        include_storage: bool = True,
    ) -> dict[str, Any]:
        terminal_statuses = {"completed", "failed", "canceled", "interaction_required"}
        start = time.time()
        while True:
            current = self.client.get_task_run(task_run_id=task_run_id, include_storage=include_storage)
            if current.get("status") in terminal_statuses:
                return current
            if (time.time() - start) > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for task run {task_run_id}")
            time.sleep(poll_seconds)

    @staticmethod
    def _policy_prompt(display_name: str) -> str:
        return (
            "Authenticate to the broker management system and retrieve policy records for the "
            "requested client reference. Return normalized policy metadata including policy number, "
            "insured/client name, insurer, product line, status, coverage dates, premium, and broker "
            f"reference. This task targets {display_name}. Collect available policy documents such as "
            "schedule, certificate, wording, and endorsements for storage capture. If a field is not "
            "available, return null for that field instead of inventing values."
        )
