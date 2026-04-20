"""Orchestration for a Deck agent that switches Verizon default payment cards."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deck_client import DeckClient

DEFAULT_VERIZON_REGISTRY_PATH = Path(".deck") / "verizon_payment_agent.json"


@dataclass(frozen=True)
class VerizonPaymentAgentRecord:
    """Stored Deck resource IDs for the Verizon payment switch workflow."""

    source_id: str
    source_url: str
    agent_id: str
    task_id: str


class VerizonPaymentAgentManager:
    """Manages provisioning and execution for Verizon payment-method switching."""

    def __init__(
        self,
        client: DeckClient,
        registry_path: str | Path = DEFAULT_VERIZON_REGISTRY_PATH,
    ) -> None:
        self.client = client
        self.registry_path = Path(registry_path)

    def load_registry(self) -> VerizonPaymentAgentRecord | None:
        if not self.registry_path.exists():
            return None
        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return VerizonPaymentAgentRecord(**raw)

    def save_registry(self, record: VerizonPaymentAgentRecord) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(vars(record), handle, indent=2, sort_keys=True)

    def bootstrap(self, *, source_url: str = "https://www.verizon.com/") -> VerizonPaymentAgentRecord:
        source = self.client.create_source(
            name="Verizon",
            website_url=source_url,
        )
        agent = self.client.create_agent(
            name="Verizon Payment Method Switch Agent",
            description=(
                "Switch the default payment method on a Verizon account to a target card "
                "already stored on file."
            ),
        )
        task = self.client.create_task(
            agent_id=agent["id"],
            name="Switch Default Card on Verizon Account",
            prompt=self._payment_switch_prompt(),
            input_schema=self._task_input_schema(),
            output_schema=self._task_output_schema(),
        )
        record = VerizonPaymentAgentRecord(
            source_id=source["id"],
            source_url=source_url,
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
    ) -> dict[str, Any]:
        registry = self.load_registry()
        if registry is None:
            raise ValueError("Verizon agent is not bootstrapped yet. Run bootstrap-verizon first.")
        return self.client.create_credential(
            source_id=registry.source_id,
            external_id=external_id,
            username=username,
            password=password,
        )

    def run_payment_method_switch(
        self,
        *,
        credential_id: str,
        target_card_last4: str,
        confirm_switch: bool,
        target_card_label: str | None = None,
        billing_zip: str | None = None,
        account_nickname: str | None = None,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        registry = self.load_registry()
        if registry is None:
            raise ValueError("Verizon agent is not bootstrapped yet. Run bootstrap-verizon first.")
        if len(target_card_last4) != 4 or not target_card_last4.isdigit():
            raise ValueError("target_card_last4 must be exactly 4 digits")
        if not confirm_switch:
            raise ValueError("confirm_switch must be true to run this operation")

        task_input: dict[str, Any] = {
            "target_card_last4": target_card_last4,
            "confirm_switch": confirm_switch,
        }
        if target_card_label:
            task_input["target_card_label"] = target_card_label
        if billing_zip:
            task_input["billing_zip"] = billing_zip
        if account_nickname:
            task_input["account_nickname"] = account_nickname

        return self.client.run_task(
            task_id=registry.task_id,
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
    ) -> dict[str, Any]:
        terminal_statuses = {"completed", "failed", "canceled", "interaction_required"}
        start = time.time()
        while True:
            current = self.client.get_task_run(task_run_id=task_run_id, include_storage=False)
            if current.get("status") in terminal_statuses:
                return current
            if (time.time() - start) > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for task run {task_run_id}")
            time.sleep(poll_seconds)

    @staticmethod
    def _payment_switch_prompt() -> str:
        return (
            "Authenticate to the Verizon account and navigate to billing or autopay settings. "
            "Locate payment methods already saved on file, identify the card matching "
            "target_card_last4 and optional target_card_label, and set it as the default card. "
            "Do not submit a bill payment. If verification is required (MFA/security challenge), "
            "request interaction input and continue once provided. Return precise outcome details "
            "including whether a switch happened, previous default card last4 when visible, and "
            "the resulting default card last4."
        )

    @staticmethod
    def _task_input_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target_card_last4": {
                    "type": "string",
                    "pattern": "^[0-9]{4}$",
                    "description": "Last four digits of the card that should become default.",
                },
                "target_card_label": {
                    "type": "string",
                    "description": "Optional nickname/label shown in Verizon for the target card.",
                },
                "billing_zip": {
                    "type": "string",
                    "description": "Optional ZIP code used to disambiguate cards if prompted.",
                },
                "account_nickname": {
                    "type": "string",
                    "description": "Optional Verizon account nickname when multiple accounts exist.",
                },
                "confirm_switch": {
                    "type": "boolean",
                    "description": "Safety confirmation. Must be true to authorize changing the default card.",
                },
            },
            "required": ["target_card_last4", "confirm_switch"],
        }

    @staticmethod
    def _task_output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "switched",
                        "already_default",
                        "card_not_found",
                        "interaction_required",
                        "failed",
                    ],
                },
                "switched": {"type": "boolean"},
                "target_card_last4": {"type": "string"},
                "previous_default_card_last4": {"type": ["string", "null"]},
                "current_default_card_last4": {"type": ["string", "null"]},
                "confirmation_message": {"type": ["string", "null"]},
                "actions_taken": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "retrieved_at": {"type": "string", "format": "date-time"},
            },
            "required": [
                "status",
                "switched",
                "target_card_last4",
                "actions_taken",
                "retrieved_at",
            ],
        }
