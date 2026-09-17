"""Import historical price data from a generic CSV.

OpenRouter's own API only reflects current prices; it does not publish a
historical price-change log. To backfill dates before you started running
this tool, point this importer at a CSV built from wherever you sourced
historical OpenRouter/provider pricing (for example, exporting rows from a
community-maintained price-history project into the columns below).

Expected columns (header required, extra columns are ignored):

    model,provider,prompt_price,completion_price,effective_date

- ``model``: OpenRouter canonical id, e.g. ``openai/gpt-4o``
- ``provider``: provider slug/name as OpenRouter reports it, e.g. ``azure``
- ``prompt_price`` / ``completion_price``: USD per token (not per 1K/1M)
- ``effective_date``: ISO 8601 date or datetime this price took effect
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .models import PriceSnapshot

REQUIRED_COLUMNS = {"model", "provider", "prompt_price", "completion_price", "effective_date"}


class CsvImportError(ValueError):
    pass


def parse_price_history_csv(path: str | Path) -> list[PriceSnapshot]:
    return parse_price_history_csv_text(Path(path).read_text())


def parse_price_history_csv_text(text: str) -> list[PriceSnapshot]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        raise CsvImportError(f"CSV is missing required columns: {sorted(missing)}")

    snapshots: list[PriceSnapshot] = []
    for line_number, row in enumerate(reader, start=2):
        try:
            snapshots.append(
                PriceSnapshot(
                    model=row["model"].strip(),
                    provider=row["provider"].strip(),
                    prompt_price=float(row["prompt_price"]),
                    completion_price=float(row["completion_price"]),
                    timestamp=row["effective_date"].strip(),
                    source="import",
                )
            )
        except (ValueError, KeyError) as exc:
            raise CsvImportError(f"Row {line_number} is invalid: {exc}") from exc
    return snapshots
