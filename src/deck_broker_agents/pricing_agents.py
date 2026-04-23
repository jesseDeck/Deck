"""High-level orchestration for retail product pricing extraction agents."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deck_client import DeckClient
from .pricing_models import RETAIL_CATALOGS, pricing_task_input_schema, pricing_task_output_schema

DEFAULT_PRICING_REGISTRY_PATH = Path(".deck") / "pricing_agents.json"


@dataclass(frozen=True)
class PricingAgentRecord:
    """Stored Deck resource IDs for one retail catalog."""

    catalog: str
    source_id: str
    source_url: str
    agent_id: str
    task_id: str


class PricingAgentManager:
    """Manages provisioning and execution of Deck pricing extraction tasks."""

    def __init__(self, client: DeckClient, registry_path: str | Path = DEFAULT_PRICING_REGISTRY_PATH) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> dict[str, PricingAgentRecord]:
        if not self.registry_path.exists():
            return {}
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {key: PricingAgentRecord(**value) for key, value in raw.items()}

    def save_registry(self, registry: dict[str, PricingAgentRecord]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        raw = {key: vars(value) for key, value in registry.items()}
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2, sort_keys=True)

    def bootstrap(self, catalog: str, *, source_url: str | None = None) -> PricingAgentRecord:
        key = catalog.lower().strip()
        if key not in RETAIL_CATALOGS:
            allowed = ", ".join(sorted(RETAIL_CATALOGS))
            raise ValueError(f"Unknown catalog '{catalog}'. Expected one of: {allowed}")

        target = RETAIL_CATALOGS[key]
        source = self.client.create_source(
            name=f"{target.display_name} Product Catalog",
            website_url=source_url or target.default_source_url,
        )
        agent = self.client.create_agent(
            name=f"{target.display_name} Pricing Extractor",
            description=(
                "Extract product pricing and availability in a normalized schema for retail "
                f"catalog data from {target.display_name}."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Extract Product Pricing",
            prompt=self._pricing_prompt(),
            input_schema=pricing_task_input_schema(),
            output_schema=pricing_task_output_schema(),
        )
        return PricingAgentRecord(
            catalog=key,
            source_id=source["id"],
            source_url=(source_url or target.default_source_url),
            agent_id=agent["id"],
            task_id=task["id"],
        )

    def bootstrap_many(
        self,
        catalogs: list[str] | None = None,
        *,
        source_url_overrides: dict[str, str] | None = None,
    ) -> dict[str, PricingAgentRecord]:
        targets = catalogs or sorted(RETAIL_CATALOGS.keys())
        source_url_overrides = source_url_overrides or {}

        registry = self.load_registry()
        for key in targets:
            normalized_key = key.lower().strip()
            record = self.bootstrap(
                normalized_key,
                source_url=source_url_overrides.get(normalized_key),
            )
            registry[normalized_key] = record
        self.save_registry(registry)
        return registry

    def create_public_credential(self, *, catalog: str, external_id: str) -> dict[str, Any]:
        key = catalog.lower().strip()
        registry = self.load_registry()
        if key not in registry:
            raise ValueError(f"{catalog} is not bootstrapped yet. Run bootstrap first so source_id is available.")
        return self.client.create_no_auth_credential(
            source_id=registry[key].source_id,
            external_id=external_id,
        )

    def run_pricing_extraction(
        self,
        *,
        catalog: str,
        categories: list[str] | None = None,
        credential_id: str | None = None,
        search_terms: list[str] | None = None,
        max_products_per_category: int = 20,
        include_out_of_stock: bool = False,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = catalog.lower().strip()
        registry = self.load_registry()
        if key not in registry:
            raise ValueError(f"{catalog} is not bootstrapped yet.")

        selected_categories = categories or list(RETAIL_CATALOGS[key].default_categories)
        task_input: dict[str, Any] = {
            "categories": selected_categories,
            "max_products_per_category": max_products_per_category,
            "include_out_of_stock": include_out_of_stock,
        }
        if search_terms:
            task_input["search_terms"] = search_terms

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
        include_storage: bool = False,
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
    def _pricing_prompt() -> str:
        return (
            "Search the source catalog for requested product categories and return product pricing data. "
            "For each matching product, capture product name, category, brand if available, SKU/model if "
            "available, current displayed price as a number, currency when visible, availability text, and "
            "the product page URL. Prioritize faucets and sinks when requested. Return null for optional "
            "fields that are not available and avoid inventing values."
        )
