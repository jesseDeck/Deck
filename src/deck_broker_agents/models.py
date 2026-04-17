"""Domain models and defaults for broker policy extraction agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerSystem:
    """Configuration describing a broker management system target."""

    key: str
    display_name: str
    default_source_url: str


BROKER_SYSTEMS: dict[str, BrokerSystem] = {
    "acturis": BrokerSystem(
        key="acturis",
        display_name="Acturis",
        default_source_url="https://www.acturis.com/",
    ),
    "open_gi": BrokerSystem(
        key="open_gi",
        display_name="Open GI",
        default_source_url="https://www.opengi.co.uk/",
    ),
    "ssp": BrokerSystem(
        key="ssp",
        display_name="SSP",
        default_source_url="https://www.ssp-worldwide.com/",
    ),
}


def task_input_schema() -> dict[str, Any]:
    """Schema for filtering policy extraction by client and policy refs."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "client_reference": {
                "type": "string",
                "description": "Client account reference in the broker management system.",
            },
            "policy_numbers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of specific policy numbers to fetch.",
            },
            "include_inactive": {
                "type": "boolean",
                "default": False,
                "description": "Whether to include lapsed/cancelled policies.",
            },
            "as_of_date": {
                "type": "string",
                "format": "date",
                "description": "Optional snapshot date for policy state.",
            },
        },
        "required": ["client_reference"],
    }


def task_output_schema() -> dict[str, Any]:
    """Schema for normalized client policy output across all broker systems."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "client_reference": {"type": "string"},
            "broker_system": {"type": "string"},
            "policies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "policy_number": {"type": "string"},
                        "client_name": {"type": "string"},
                        "insurer_name": {"type": "string"},
                        "product_line": {"type": "string"},
                        "status": {"type": "string"},
                        "inception_date": {"type": ["string", "null"], "format": "date"},
                        "expiry_date": {"type": ["string", "null"], "format": "date"},
                        "premium_amount": {"type": ["number", "null"]},
                        "currency": {"type": ["string", "null"]},
                        "broker_reference": {"type": ["string", "null"]},
                        "documents": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                                "required": ["name", "type"],
                            },
                        },
                    },
                    "required": [
                        "policy_number",
                        "client_name",
                        "insurer_name",
                        "product_line",
                        "status",
                        "documents",
                    ],
                },
            },
            "retrieved_at": {"type": "string", "format": "date-time"},
        },
        "required": ["client_reference", "broker_system", "policies", "retrieved_at"],
    }


def storage_extraction_schema() -> dict[str, Any]:
    """Schema for extracting structure from captured policy documents."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "policy_number": {"type": "string"},
            "document_type": {"type": "string"},
            "insured_name": {"type": "string"},
            "insurer_name": {"type": "string"},
            "effective_date": {"type": ["string", "null"], "format": "date"},
            "expiry_date": {"type": ["string", "null"], "format": "date"},
            "premium_amount": {"type": ["number", "null"]},
            "currency": {"type": ["string", "null"]},
        },
        "required": ["policy_number", "document_type"],
    }
