"""Domain models and defaults for broker and healthcare extraction agents."""

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

DEFAULT_ATHENA_SOURCE_URL = "https://athenanet.athenahealth.com/"
ATHENA_MEDICAL_RECORD_SECTIONS = (
    "demographics",
    "encounters",
    "problems",
    "medications",
    "allergies",
    "labs",
    "immunizations",
    "vitals",
    "documents",
)


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


def athena_medical_record_input_schema() -> dict[str, Any]:
    """Schema for pulling a patient chart from Athenahealth."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "patient_reference": {
                "type": "string",
                "description": "Patient identifier used by the practice (MRN or patient ID).",
            },
            "date_from": {
                "type": "string",
                "format": "date",
                "description": "Optional lower date boundary for record retrieval.",
            },
            "date_to": {
                "type": "string",
                "format": "date",
                "description": "Optional upper date boundary for record retrieval.",
            },
            "include_sections": {
                "type": "array",
                "items": {"type": "string", "enum": list(ATHENA_MEDICAL_RECORD_SECTIONS)},
                "description": "Optional record sections to return. Defaults to all available sections.",
            },
        },
        "required": ["patient_reference"],
    }


def athena_medical_record_output_schema() -> dict[str, Any]:
    """Schema for normalized patient record output from Athenahealth."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_system": {"type": "string"},
            "patient": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "patient_reference": {"type": "string"},
                    "full_name": {"type": ["string", "null"]},
                    "date_of_birth": {"type": ["string", "null"], "format": "date"},
                    "sex": {"type": ["string", "null"]},
                },
                "required": ["patient_reference"],
            },
            "records": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "encounters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "date": {"type": ["string", "null"], "format": "date"},
                                "type": {"type": ["string", "null"]},
                                "provider": {"type": ["string", "null"]},
                                "summary": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "problems": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "status": {"type": ["string", "null"]},
                                "onset_date": {"type": ["string", "null"], "format": "date"},
                            },
                            "required": ["name"],
                        },
                    },
                    "medications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "sig": {"type": ["string", "null"]},
                                "status": {"type": ["string", "null"]},
                            },
                            "required": ["name"],
                        },
                    },
                    "allergies": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "allergen": {"type": "string"},
                                "reaction": {"type": ["string", "null"]},
                                "severity": {"type": ["string", "null"]},
                            },
                            "required": ["allergen"],
                        },
                    },
                    "labs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": ["string", "null"]},
                                "units": {"type": ["string", "null"]},
                                "date": {"type": ["string", "null"], "format": "date"},
                            },
                            "required": ["name"],
                        },
                    },
                    "immunizations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "date": {"type": ["string", "null"], "format": "date"},
                                "status": {"type": ["string", "null"]},
                            },
                            "required": ["name"],
                        },
                    },
                    "vitals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "date": {"type": ["string", "null"], "format": "date"},
                                "measurement": {"type": "string"},
                                "value": {"type": ["string", "null"]},
                            },
                            "required": ["measurement"],
                        },
                    },
                    "documents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "document_type": {"type": ["string", "null"]},
                                "date": {"type": ["string", "null"], "format": "date"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": [
                    "encounters",
                    "problems",
                    "medications",
                    "allergies",
                    "labs",
                    "immunizations",
                    "vitals",
                    "documents",
                ],
            },
            "retrieved_at": {"type": "string", "format": "date-time"},
        },
        "required": ["source_system", "patient", "records", "retrieved_at"],
    }


def athena_storage_extraction_schema() -> dict[str, Any]:
    """Schema for extraction from captured Athenahealth chart documents."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "patient_reference": {"type": "string"},
            "document_name": {"type": "string"},
            "document_type": {"type": ["string", "null"]},
            "document_date": {"type": ["string", "null"], "format": "date"},
            "summary": {"type": ["string", "null"]},
        },
        "required": ["patient_reference", "document_name"],
    }
