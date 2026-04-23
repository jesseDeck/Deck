"""Domain models and schemas for product pricing extraction agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetailCatalog:
    """Configuration describing an e-commerce catalog target."""

    key: str
    display_name: str
    default_source_url: str
    default_categories: tuple[str, ...]


RETAIL_CATALOGS: dict[str, RetailCatalog] = {
    "ferguson": RetailCatalog(
        key="ferguson",
        display_name="Ferguson",
        default_source_url="https://www.ferguson.com/",
        default_categories=("faucets", "sinks"),
    ),
}


def pricing_task_input_schema() -> dict[str, Any]:
    """Schema for category and keyword-driven pricing extraction."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "categories": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
                "description": "Product categories to collect prices for, e.g. faucets, sinks.",
            },
            "search_terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional keyword filters (brand, style, finish, etc).",
            },
            "max_products_per_category": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 20,
                "description": "Maximum number of products to return for each category.",
            },
            "include_out_of_stock": {
                "type": "boolean",
                "default": False,
                "description": "Whether to include products marked out of stock/unavailable.",
            },
        },
        "required": ["categories"],
    }


def pricing_task_output_schema() -> dict[str, Any]:
    """Schema for normalized product pricing output."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "catalog": {"type": "string"},
            "queried_categories": {
                "type": "array",
                "items": {"type": "string"},
            },
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "category": {"type": "string"},
                        "name": {"type": "string"},
                        "brand": {"type": ["string", "null"]},
                        "sku": {"type": ["string", "null"]},
                        "price": {"type": "number"},
                        "currency": {"type": ["string", "null"]},
                        "availability": {"type": ["string", "null"]},
                        "product_url": {"type": "string"},
                    },
                    "required": ["category", "name", "price", "product_url"],
                },
            },
            "retrieved_at": {"type": "string", "format": "date-time"},
        },
        "required": ["catalog", "queried_categories", "products", "retrieved_at"],
    }
