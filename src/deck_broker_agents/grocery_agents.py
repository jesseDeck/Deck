"""High-level orchestration for Canadian grocery profile extraction agents."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deck_client import DeckClient
from .models import (
    CANADIAN_GROCERY_CHAINS,
    grocery_profile_input_schema,
    grocery_profile_output_schema,
    grocery_storage_extraction_schema,
)

DEFAULT_GROCERY_REGISTRY_PATH = Path(".deck") / "grocery_agents.json"


@dataclass(frozen=True)
class GroceryAgentRecord:
    """Stored Deck resource IDs for one grocery chain."""

    grocery_chain: str
    source_id: str
    source_url: str
    agent_id: str
    task_id: str


class GroceryAgentManager:
    """Manages provisioning and execution of Deck grocery profile extraction tasks."""

    def __init__(
        self,
        client: DeckClient,
        registry_path: str | Path = DEFAULT_GROCERY_REGISTRY_PATH,
    ) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> dict[str, GroceryAgentRecord]:
        if not self.registry_path.exists():
            return {}
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {key: GroceryAgentRecord(**value) for key, value in raw.items()}

    def save_registry(self, registry: dict[str, GroceryAgentRecord]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        raw = {key: vars(value) for key, value in registry.items()}
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2, sort_keys=True)

    def bootstrap(
        self,
        grocery_chain: str,
        *,
        source_url: str | None = None,
    ) -> GroceryAgentRecord:
        key = grocery_chain.lower().strip()
        if key not in CANADIAN_GROCERY_CHAINS:
            allowed = ", ".join(sorted(CANADIAN_GROCERY_CHAINS))
            raise ValueError(f"Unknown grocery_chain '{grocery_chain}'. Expected one of: {allowed}")

        chain = CANADIAN_GROCERY_CHAINS[key]
        source = self.client.create_source(
            name=f"{chain.display_name} Customer Portal",
            website_url=source_url or chain.default_source_url,
        )
        agent = self.client.create_agent(
            name=f"{chain.display_name} Profile Data Extractor",
            description=(
                "Extract customer profile records and account metadata in a normalized schema "
                f"from {chain.display_name}."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Extract Customer Profile Data",
            prompt=self._profile_prompt(chain.display_name),
            input_schema=grocery_profile_input_schema(),
            output_schema=grocery_profile_output_schema(),
            storage={
                "enabled": True,
                "extraction": True,
                "deduplication": True,
                "extraction_schema": grocery_storage_extraction_schema(),
            },
        )
        return GroceryAgentRecord(
            grocery_chain=key,
            source_id=source["id"],
            source_url=(source_url or chain.default_source_url),
            agent_id=agent["id"],
            task_id=task["id"],
        )

    def bootstrap_many(
        self,
        grocery_chains: list[str] | None = None,
        *,
        source_url_overrides: dict[str, str] | None = None,
    ) -> dict[str, GroceryAgentRecord]:
        chains = grocery_chains or sorted(CANADIAN_GROCERY_CHAINS.keys())
        source_url_overrides = source_url_overrides or {}

        registry = self.load_registry()
        for key in chains:
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
        grocery_chain: str,
        external_id: str,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        registry = self.load_registry()
        key = grocery_chain.lower().strip()
        if key not in registry:
            raise ValueError(
                f"{grocery_chain} is not bootstrapped yet. Run bootstrap first so source_id is available."
            )
        return self.client.create_credential(
            source_id=registry[key].source_id,
            external_id=external_id,
            username=username,
            password=password,
        )

    def run_profile_extraction(
        self,
        *,
        grocery_chain: str,
        credential_id: str,
        customer_reference: str,
        include_loyalty: bool = True,
        include_addresses: bool = True,
        include_payment_methods: bool = False,
        include_marketing_preferences: bool = True,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = grocery_chain.lower().strip()
        registry = self.load_registry()
        if key not in registry:
            raise ValueError(f"{grocery_chain} is not bootstrapped yet.")

        task_input: dict[str, Any] = {
            "customer_reference": customer_reference,
            "include_loyalty": include_loyalty,
            "include_addresses": include_addresses,
            "include_payment_methods": include_payment_methods,
            "include_marketing_preferences": include_marketing_preferences,
        }
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
    def _profile_prompt(display_name: str) -> str:
        return (
            "Authenticate to the grocery customer account and retrieve profile data for the requested "
            "customer reference. Return normalized profile metadata including account identifiers, full "
            "name, email, phone, loyalty membership details, addresses, payment method summaries, and "
            f"communication preferences. This task targets {display_name}. Capture available profile "
            "or account documents for storage when present. If a field is not available, return null "
            "for that field instead of inventing values."
        )
