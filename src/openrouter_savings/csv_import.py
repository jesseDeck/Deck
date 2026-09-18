"""CSV backfill importers for historical pricing and downtime.

Both importers are deliberately source-agnostic rather than built against any
one site's API: this project's sandbox couldn't reach third-party sites like
benchlm.ai or isitdown.ai to verify their exact API schemas, so rather than
guess and risk silently-wrong numbers, these accept a plain CSV you export or
paste from wherever you sourced the data.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .models import DowntimeIncident, PriceSnapshot

PRICE_REQUIRED_COLUMNS = {"model", "provider", "prompt_price", "completion_price", "effective_date"}
DOWNTIME_REQUIRED_COLUMNS = {"model", "provider", "start", "end"}


class CsvImportError(ValueError):
    pass


def parse_price_history_csv(path: str | Path) -> list[PriceSnapshot]:
    return parse_price_history_csv_text(Path(path).read_text())


def parse_price_history_csv_text(text: str) -> list[PriceSnapshot]:
    """Parse historical prompt/completion pricing.

    Expected columns: ``model,provider,prompt_price,completion_price,effective_date``
    (USD per token, ISO 8601 date/datetime).
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not PRICE_REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        missing = PRICE_REQUIRED_COLUMNS - set(reader.fieldnames or [])
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


def parse_downtime_incidents_csv(path: str | Path) -> list[DowntimeIncident]:
    return parse_downtime_incidents_csv_text(Path(path).read_text())


def parse_downtime_incidents_csv_text(text: str) -> list[DowntimeIncident]:
    """Parse a discrete outage-window log.

    Expected columns: ``model,provider,start,end`` (ISO 8601 datetimes), plus
    optional ``notes``. Useful for backfilling outage history from a status
    or incident-monitoring source, since this tool's own uptime polling only
    covers time after you started tracking a model.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not DOWNTIME_REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        missing = DOWNTIME_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        raise CsvImportError(f"CSV is missing required columns: {sorted(missing)}")

    incidents: list[DowntimeIncident] = []
    for line_number, row in enumerate(reader, start=2):
        try:
            incidents.append(
                DowntimeIncident(
                    model=row["model"].strip(),
                    provider=row["provider"].strip(),
                    start=row["start"].strip(),
                    end=row["end"].strip(),
                    source="import",
                    notes=(row.get("notes") or "").strip(),
                )
            )
        except KeyError as exc:
            raise CsvImportError(f"Row {line_number} is invalid: {exc}") from exc
    return incidents
