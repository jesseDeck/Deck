"""Domain models and defaults for Deck extraction agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerSystem:
    """Configuration describing a broker management system target."""

    key: str
    display_name: str
    default_source_url: str


@dataclass(frozen=True)
class GroceryChain:
    """Configuration describing a Canadian grocery chain target."""

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


GROCERY_CHAINS: dict[str, GroceryChain] = {
    "loblaw": GroceryChain(
        key="loblaw",
        display_name="Loblaw",
        default_source_url="https://www.pcoptimum.ca/",
    ),
    "sobeys": GroceryChain(
        key="sobeys",
        display_name="Sobeys",
        default_source_url="https://www.sceneplus.ca/",
    ),
    "metro": GroceryChain(
        key="metro",
        display_name="Metro",
        default_source_url="https://www.metro.ca/en/my-metro.html",
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


def grocery_task_input_schema() -> dict[str, Any]:
    """Schema for profile extraction by customer reference."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "customer_reference": {
                "type": "string",
                "description": "Customer identifier such as account email or loyalty profile ID.",
            },
            "include_order_history": {
                "type": "boolean",
                "default": False,
                "description": "Whether to include recent order summaries.",
            },
            "max_orders": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
                "description": "Maximum number of recent orders to include when order history is enabled.",
            },
            "include_saved_addresses": {
                "type": "boolean",
                "default": True,
                "description": "Whether to include saved address entries from the customer profile.",
            },
            "as_of_date": {
                "type": "string",
                "format": "date",
                "description": "Optional snapshot date for profile retrieval.",
            },
        },
        "required": ["customer_reference"],
    }


def grocery_task_output_schema() -> dict[str, Any]:
    """Schema for normalized grocery customer profile output."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "customer_reference": {"type": "string"},
            "grocery_chain": {"type": "string"},
            "profile": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "first_name": {"type": ["string", "null"]},
                    "last_name": {"type": ["string", "null"]},
                    "email": {"type": ["string", "null"]},
                    "phone": {"type": ["string", "null"]},
                    "loyalty_id": {"type": ["string", "null"]},
                    "account_status": {"type": ["string", "null"]},
                    "preferred_store_id": {"type": ["string", "null"]},
                    "preferred_store_name": {"type": ["string", "null"]},
                    "points_balance": {"type": ["number", "null"]},
                    "points_program_name": {"type": ["string", "null"]},
                    "marketing_email_opt_in": {"type": ["boolean", "null"]},
                    "marketing_sms_opt_in": {"type": ["boolean", "null"]},
                    "addresses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "label": {"type": ["string", "null"]},
                                "line1": {"type": ["string", "null"]},
                                "line2": {"type": ["string", "null"]},
                                "city": {"type": ["string", "null"]},
                                "province": {"type": ["string", "null"]},
                                "postal_code": {"type": ["string", "null"]},
                                "country": {"type": ["string", "null"]},
                                "is_default": {"type": ["boolean", "null"]},
                            },
                            "required": [
                                "label",
                                "line1",
                                "line2",
                                "city",
                                "province",
                                "postal_code",
                                "country",
                                "is_default",
                            ],
                        },
                    },
                },
                "required": [
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "loyalty_id",
                    "account_status",
                    "preferred_store_id",
                    "preferred_store_name",
                    "points_balance",
                    "points_program_name",
                    "marketing_email_opt_in",
                    "marketing_sms_opt_in",
                    "addresses",
                ],
            },
            "recent_orders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "order_id": {"type": "string"},
                        "order_date": {"type": ["string", "null"], "format": "date-time"},
                        "order_total": {"type": ["number", "null"]},
                        "currency": {"type": ["string", "null"]},
                        "item_count": {"type": ["integer", "null"]},
                        "store_name": {"type": ["string", "null"]},
                    },
                    "required": [
                        "order_id",
                        "order_date",
                        "order_total",
                        "currency",
                        "item_count",
                        "store_name",
                    ],
                },
            },
            "retrieved_at": {"type": "string", "format": "date-time"},
        },
        "required": ["customer_reference", "grocery_chain", "profile", "recent_orders", "retrieved_at"],
    }


def grocery_storage_extraction_schema() -> dict[str, Any]:
    """Schema for extracting structure from captured grocery receipts/documents."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "order_id": {"type": "string"},
            "purchase_date": {"type": ["string", "null"], "format": "date"},
            "store_name": {"type": ["string", "null"]},
            "loyalty_id": {"type": ["string", "null"]},
            "subtotal_amount": {"type": ["number", "null"]},
            "tax_amount": {"type": ["number", "null"]},
            "total_amount": {"type": ["number", "null"]},
            "currency": {"type": ["string", "null"]},
        },
        "required": ["order_id"],
    }
