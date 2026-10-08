"""Domain models and schemas for healthcare claims extraction agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClaimsSource:
    """Configuration describing a payer or patient portal target."""

    key: str
    display_name: str
    default_source_url: str
    portal_type: str  # "payer" (insurer member portal) or "provider" (patient/billing portal)
    tenant_specific: bool = False  # True when each practice/health system has its own login URL


CLAIMS_SOURCES: dict[str, ClaimsSource] = {
    "cigna": ClaimsSource(
        key="cigna",
        display_name="Cigna",
        default_source_url="https://my.cigna.com/",
        portal_type="payer",
    ),
    "aetna": ClaimsSource(
        key="aetna",
        display_name="Aetna",
        default_source_url="https://health.aetna.com/",
        portal_type="payer",
    ),
    "uhc": ClaimsSource(
        key="uhc",
        display_name="UnitedHealthcare (myUHC)",
        default_source_url="https://www.myuhc.com/",
        portal_type="payer",
    ),
    "elevance": ClaimsSource(
        key="elevance",
        display_name="Elevance Health (Anthem)",
        default_source_url="https://www.anthem.com/login/",
        portal_type="payer",
    ),
    "hcsc": ClaimsSource(
        key="hcsc",
        display_name="HCSC Blue Access for Members",
        # HCSC runs Blue Access for Members per state plan (IL, TX, OK, NM, MT).
        default_source_url="https://www.bcbsil.com/",
        portal_type="payer",
        tenant_specific=True,
    ),
    "highmark": ClaimsSource(
        key="highmark",
        display_name="Highmark",
        default_source_url="https://www.highmark.com/",
        portal_type="payer",
    ),
    "mychart": ClaimsSource(
        key="mychart",
        display_name="MyChart (Epic)",
        # Each health system hosts its own MyChart; this is Epic's portal finder.
        default_source_url="https://www.mychart.org/",
        portal_type="provider",
        tenant_specific=True,
    ),
    "athena": ClaimsSource(
        key="athena",
        display_name="athenaPatient",
        default_source_url="https://myhealth.athenahealth.com/",
        portal_type="provider",
    ),
    "mypatientportal": ClaimsSource(
        key="mypatientportal",
        display_name="MyPatientPortal",
        default_source_url="https://www.mypatientportal.com/",
        portal_type="provider",
        tenant_specific=True,
    ),
    "eclinicalworks": ClaimsSource(
        key="eclinicalworks",
        display_name="eClinicalWorks (healow)",
        default_source_url="https://healow.com/",
        portal_type="provider",
        tenant_specific=True,
    ),
}


def claims_task_input_schema() -> dict[str, Any]:
    """Schema for date-range driven claims retrieval."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "service_date_from": {
                "type": ["string", "null"],
                "format": "date",
                "description": "Earliest date of service to include (YYYY-MM-DD). Omit for all available history.",
            },
            "service_date_to": {
                "type": ["string", "null"],
                "format": "date",
                "description": "Latest date of service to include (YYYY-MM-DD). Omit for today.",
            },
            "member_name": {
                "type": ["string", "null"],
                "description": "Optional family member/dependent to filter to. Omit to include all members on the account.",
            },
            "claim_statuses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional status filter (e.g. processed, pending, denied). Omit for all statuses.",
            },
            "max_claims": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 200,
                "description": "Maximum number of claims/statements to return.",
            },
            "download_eobs": {
                "type": "boolean",
                "default": True,
                "description": "Download EOB or itemized statement PDFs to storage when available.",
            },
        },
    }


def _money(description: str) -> dict[str, Any]:
    return {"type": ["number", "null"], "description": description}


def claims_task_output_schema() -> dict[str, Any]:
    """Schema for normalized claims output shared by payer and provider portals."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source": {"type": "string"},
            "account_holder_name": {"type": ["string", "null"]},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "claim_id": {
                            "type": "string",
                            "description": "Claim number, or statement/encounter ID on provider portals.",
                        },
                        "record_type": {
                            "type": "string",
                            "enum": ["claim", "statement"],
                            "description": "claim for payer portals, statement for provider billing records.",
                        },
                        "status": {"type": ["string", "null"]},
                        "claim_type": {
                            "type": ["string", "null"],
                            "description": "e.g. medical, pharmacy, dental, vision, behavioral health.",
                        },
                        "plan_name": {"type": ["string", "null"]},
                        "patient_name": {"type": ["string", "null"]},
                        "provider_name": {"type": ["string", "null"]},
                        "service_date": {"type": ["string", "null"], "format": "date"},
                        "service_date_end": {"type": ["string", "null"], "format": "date"},
                        "processed_date": {"type": ["string", "null"], "format": "date"},
                        "billed_amount": _money("Total amount the provider billed/charged."),
                        "allowed_amount": _money("Amount allowed under the plan's negotiated rate."),
                        "plan_paid_amount": _money("Amount the insurance plan paid."),
                        "patient_responsibility": _money(
                            "Total the member/patient owes (deductible + copay + coinsurance + not covered)."
                        ),
                        "deductible_amount": _money("Portion of patient responsibility applied to deductible."),
                        "copay_amount": _money("Portion of patient responsibility that is copay."),
                        "coinsurance_amount": _money("Portion of patient responsibility that is coinsurance."),
                        "not_covered_amount": _money("Amount not covered by the plan."),
                        "patient_paid_amount": _money("Amount the patient has already paid, if shown."),
                        "patient_balance_due": _money("Outstanding balance still owed, if shown."),
                        "currency": {"type": ["string", "null"]},
                        "eob_available": {"type": ["boolean", "null"]},
                    },
                    "required": [
                        "claim_id",
                        "record_type",
                        "status",
                        "claim_type",
                        "plan_name",
                        "provider_name",
                        "service_date",
                        "billed_amount",
                        "plan_paid_amount",
                        "patient_responsibility",
                    ],
                },
            },
            "retrieved_at": {"type": "string", "format": "date-time"},
        },
        "required": ["source", "claims", "retrieved_at"],
    }


def claims_storage_extraction_schema() -> dict[str, Any]:
    """Schema for extracting structure from downloaded EOB / statement documents."""
    return {
        "type": "object",
        "properties": {
            "claim_id": {"type": "string"},
            "document_type": {"type": "string"},
            "patient_name": {"type": ["string", "null"]},
            "provider_name": {"type": ["string", "null"]},
            "service_date": {"type": ["string", "null"], "format": "date"},
            "billed_amount": {"type": ["number", "null"]},
            "plan_paid_amount": {"type": ["number", "null"]},
            "patient_responsibility": {"type": ["number", "null"]},
            "currency": {"type": ["string", "null"]},
        },
        "required": ["claim_id", "document_type"],
    }
