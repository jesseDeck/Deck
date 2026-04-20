"""High-level orchestration for Athenahealth medical record extraction agents."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deck_client import DeckClient
from .models import (
    ATHENA_MEDICAL_RECORD_SECTIONS,
    DEFAULT_ATHENA_SOURCE_URL,
    athena_medical_record_input_schema,
    athena_medical_record_output_schema,
    athena_storage_extraction_schema,
)

DEFAULT_ATHENA_REGISTRY_PATH = Path(".deck") / "athena_agent.json"


@dataclass(frozen=True)
class AthenaHealthRecord:
    """Stored Deck resource IDs for Athenahealth extraction."""

    source_id: str
    source_url: str
    agent_id: str
    task_id: str


class AthenaHealthAgentManager:
    """Manages provisioning and execution of Athenahealth extraction tasks."""

    def __init__(self, client: DeckClient, registry_path: str | Path = DEFAULT_ATHENA_REGISTRY_PATH) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> AthenaHealthRecord | None:
        if not self.registry_path.exists():
            return None
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return AthenaHealthRecord(**raw)

    def save_registry(self, record: AthenaHealthRecord) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(vars(record), handle, indent=2, sort_keys=True)

    def bootstrap(self, *, source_url: str | None = None) -> AthenaHealthRecord:
        resolved_source_url = source_url or DEFAULT_ATHENA_SOURCE_URL
        source = self.client.create_source(
            name="Athenahealth EHR Portal",
            website_url=resolved_source_url,
        )
        agent = self.client.create_agent(
            name="Athenahealth Medical Record Extractor",
            description=(
                "Extract patient medical records from Athenahealth in a normalized schema "
                "for downstream processing."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Extract Patient Medical Record",
            prompt=self._medical_record_prompt(),
            input_schema=athena_medical_record_input_schema(),
            output_schema=athena_medical_record_output_schema(),
            storage={
                "enabled": True,
                "extraction": True,
                "deduplication": True,
                "extraction_schema": athena_storage_extraction_schema(),
            },
        )
        record = AthenaHealthRecord(
            source_id=source["id"],
            source_url=resolved_source_url,
            agent_id=agent["id"],
            task_id=task["id"],
        )
        self.save_registry(record)
        return record

    def create_user_credential(
        self,
        *,
        external_id: str,
        username: str,
        password: str,
        source_fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        record = self.load_registry()
        if record is None:
            raise ValueError("Athenahealth is not bootstrapped yet. Run bootstrap-athena first.")
        return self.client.create_credential(
            source_id=record.source_id,
            external_id=external_id,
            username=username,
            password=password,
            source_fields=source_fields,
        )

    def run_medical_record_extraction(
        self,
        *,
        credential_id: str,
        patient_reference: str,
        date_from: str | None = None,
        date_to: str | None = None,
        include_sections: list[str] | None = None,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        record = self.load_registry()
        if record is None:
            raise ValueError("Athenahealth is not bootstrapped yet. Run bootstrap-athena first.")

        task_input: dict[str, Any] = {
            "patient_reference": patient_reference,
        }
        if include_sections:
            normalized_sections = [section.strip().lower() for section in include_sections if section.strip()]
            invalid_sections = sorted(set(normalized_sections) - set(ATHENA_MEDICAL_RECORD_SECTIONS))
            if invalid_sections:
                allowed = ", ".join(ATHENA_MEDICAL_RECORD_SECTIONS)
                raise ValueError(
                    f"Invalid include section(s): {', '.join(invalid_sections)}. Allowed values: {allowed}"
                )
            task_input["include_sections"] = normalized_sections
        if date_from:
            task_input["date_from"] = date_from
        if date_to:
            task_input["date_to"] = date_to

        return self.client.run_task(
            task_id=record.task_id,
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
    def _medical_record_prompt() -> str:
        return (
            "Authenticate to the source EHR and retrieve the patient chart for the supplied "
            "patient_reference. Return normalized data for demographics, encounters, active and "
            "historical conditions, medications, allergies, labs, immunizations, vitals, and chart "
            "documents. Respect optional date filters and section filters when present. Do not "
            "invent clinical values; return null when data is unavailable."
        )
