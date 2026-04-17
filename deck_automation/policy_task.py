"""Shared policy extraction task definition used during provisioning."""

from __future__ import annotations

from typing import Any


TASK_NAME = "Extract Policy Data"
TASK_PROMPT = (
    "Log in to the broker management source and extract policy records that match "
    "the provided filters. Return one item per policy with normalized fields. "
    "When a field is unavailable in the source, return null for that field."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "from_date": {
            "type": "string",
            "description": "Inclusive policy start-date lower bound (ISO 8601 date).",
        },
        "to_date": {
            "type": "string",
            "description": "Inclusive policy start-date upper bound (ISO 8601 date).",
        },
        "policy_number": {
            "type": ["string", "null"],
            "description": "Optional exact policy number filter.",
        },
        "client_name": {
            "type": ["string", "null"],
            "description": "Optional insured/customer name filter.",
        },
        "include_cancelled": {
            "type": "boolean",
            "description": "When true, include cancelled policies in the result set.",
            "default": False,
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 500,
            "description": "Maximum number of policies to return.",
            "default": 100,
        },
    },
    "required": ["from_date", "to_date"],
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "policies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "policy_number": {"type": ["string", "null"]},
                    "insurer": {"type": ["string", "null"]},
                    "product": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                    "inception_date": {"type": ["string", "null"]},
                    "renewal_date": {"type": ["string", "null"]},
                    "premium_gbp": {"type": ["number", "null"]},
                    "commission_gbp": {"type": ["number", "null"]},
                    "client_name": {"type": ["string", "null"]},
                    "source_system": {"type": ["string", "null"]},
                    "captured_at": {"type": ["string", "null"]},
                },
                "required": [
                    "policy_number",
                    "insurer",
                    "product",
                    "status",
                    "inception_date",
                    "renewal_date",
                    "premium_gbp",
                    "commission_gbp",
                    "client_name",
                    "source_system",
                    "captured_at",
                ],
            },
        },
        "page_metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "record_count": {"type": "integer"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["record_count", "warnings"],
        },
    },
    "required": ["policies", "page_metadata"],
}
