"""High-level orchestration for healthcare claims extraction agents."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .claims_models import (
    CLAIMS_SOURCES,
    ClaimsSource,
    claims_storage_extraction_schema,
    claims_task_input_schema,
    claims_task_output_schema,
)
from .deck_client import DeckClient

DEFAULT_CLAIMS_REGISTRY_PATH = Path(".deck") / "claims_agents.json"


@dataclass(frozen=True)
class ClaimsAgentRecord:
    """Stored Deck resource IDs for one payer or patient portal."""

    portal: str
    source_id: str
    source_url: str
    agent_id: str
    task_id: str


class ClaimsAgentManager:
    """Manages provisioning and execution of Deck claims extraction tasks."""

    def __init__(self, client: DeckClient, registry_path: str | Path = DEFAULT_CLAIMS_REGISTRY_PATH) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> dict[str, ClaimsAgentRecord]:
        if not self.registry_path.exists():
            return {}
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {key: ClaimsAgentRecord(**value) for key, value in raw.items()}

    def save_registry(self, registry: dict[str, ClaimsAgentRecord]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        raw = {key: vars(value) for key, value in registry.items()}
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2, sort_keys=True)

    @staticmethod
    def _resolve(portal: str) -> tuple[str, ClaimsSource]:
        key = portal.lower().strip()
        if key not in CLAIMS_SOURCES:
            allowed = ", ".join(sorted(CLAIMS_SOURCES))
            raise ValueError(f"Unknown portal '{portal}'. Expected one of: {allowed}")
        return key, CLAIMS_SOURCES[key]

    def bootstrap(self, portal: str, *, source_url: str | None = None) -> ClaimsAgentRecord:
        key, target = self._resolve(portal)
        resolved_url = source_url or target.default_source_url

        source = self.client.create_source(
            name=f"{target.display_name} Claims",
            website_url=resolved_url,
        )
        agent = self.client.create_agent(
            name=f"{target.display_name} Claims Extractor",
            description=(
                f"Retrieve the member's medical claims or billing statements from {target.display_name}, "
                "including billed amount, plan paid amount, and patient responsibility."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Extract Claims",
            prompt=self._claims_prompt(target),
            input_schema=claims_task_input_schema(),
            output_schema=claims_task_output_schema(),
            storage={
                "enabled": True,
                "extraction": True,
                "deduplication": True,
                "extraction_schema": claims_storage_extraction_schema(),
            },
        )
        return ClaimsAgentRecord(
            portal=key,
            source_id=source["id"],
            source_url=resolved_url,
            agent_id=agent["id"],
            task_id=task["id"],
        )

    def bootstrap_many(
        self,
        portals: list[str] | None = None,
        *,
        source_url_overrides: dict[str, str] | None = None,
    ) -> dict[str, ClaimsAgentRecord]:
        targets = [self._resolve(p)[0] for p in (portals or sorted(CLAIMS_SOURCES))]
        source_url_overrides = source_url_overrides or {}

        registry = self.load_registry()
        for key in targets:
            if key in registry and key not in source_url_overrides:
                # Already provisioned; skip so re-running doesn't create duplicates in Deck.
                continue
            registry[key] = self.bootstrap(key, source_url=source_url_overrides.get(key))
            # Save after each portal so a mid-run failure doesn't orphan resources already created.
            self.save_registry(registry)
        return registry

    def create_user_credential(
        self,
        *,
        portal: str,
        external_id: str,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        key, _ = self._resolve(portal)
        registry = self.load_registry()
        if key not in registry:
            raise ValueError(f"{portal} is not bootstrapped yet. Run claims-bootstrap first so source_id is available.")
        return self.client.create_credential(
            source_id=registry[key].source_id,
            external_id=external_id,
            username=username,
            password=password,
        )

    def run_claims_extraction(
        self,
        *,
        portal: str,
        credential_id: str,
        service_date_from: str | None = None,
        service_date_to: str | None = None,
        member_name: str | None = None,
        claim_statuses: list[str] | None = None,
        max_claims: int = 200,
        download_eobs: bool = True,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key, _ = self._resolve(portal)
        registry = self.load_registry()
        if key not in registry:
            raise ValueError(f"{portal} is not bootstrapped yet.")

        task_input: dict[str, Any] = {
            "max_claims": max_claims,
            "download_eobs": download_eobs,
        }
        if service_date_from:
            task_input["service_date_from"] = service_date_from
        if service_date_to:
            task_input["service_date_to"] = service_date_to
        if member_name:
            task_input["member_name"] = member_name
        if claim_statuses:
            task_input["claim_statuses"] = claim_statuses

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
        timeout_seconds: int = 900,
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
    def _claims_prompt(target: ClaimsSource) -> str:
        common = (
            f"Sign in to {target.display_name} with the provided credential and retrieve every claim "
            "within the requested service date range (all available history if no range is given), for "
            "all members on the account unless a member name is specified. Open each claim's detail view "
            "when the list view does not show the full financial breakdown. For each record capture: "
            "claim ID, status, claim type, plan name, patient name, provider name, service date, billed "
            "amount, allowed amount, plan paid amount, and patient/member responsibility. Patient "
            "responsibility is the most important field: report the total the member owes, and break it "
            "down into deductible, copay, coinsurance, and not-covered amounts whenever the portal shows "
            "them. Record amounts as plain numbers without currency symbols. "
        )
        if target.portal_type == "provider":
            specific = (
                "This is a provider patient portal, so claims usually appear under Billing, Statements, "
                "or Visits. Treat each billed visit or statement line as a record with record_type "
                "'statement'; use the statement or encounter number as claim_id, the insurance payment "
                "as plan paid amount, and the patient portion or balance as patient responsibility. "
            )
        else:
            specific = (
                "This is an insurer member portal; use record_type 'claim' and the payer's claim number. "
            )
        if target.tenant_specific:
            specific += (
                "This portal is hosted per organization; if the start page is a portal finder, use the "
                "organization associated with the credential. "
            )
        closing = (
            "When download_eobs is true, download the Explanation of Benefits or itemized statement PDF "
            "for each record. If a multi-factor or security prompt appears, request it as an interaction. "
            "Return null for any field the portal does not show; never estimate or invent values."
        )
        return common + specific + closing
