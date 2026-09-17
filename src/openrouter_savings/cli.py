"""CLI entrypoint for the OpenRouter savings & downtime calculator."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from .csv_import import CsvImportError, parse_price_history_csv
from .openrouter_client import OpenRouterClient
from .savings import compute_savings
from .server import serve
from .snapshot_job import take_snapshot
from .storage import Store
from .uptime import summarize_uptime


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenRouter savings & downtime calculator")
    parser.add_argument(
        "--data-dir",
        default=".openrouter_savings",
        help="Directory where usage entries and polled snapshots are stored.",
    )
    parser.add_argument("--base-url", default=None, help="Override OpenRouter API base URL.")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_cmd = sub.add_parser("serve", help="Run the local web app")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8787)
    serve_cmd.add_argument(
        "--poll-interval-minutes",
        type=float,
        default=None,
        help="If set, poll OpenRouter for tracked models on this interval while serving.",
    )

    sub.add_parser("snapshot", help="Poll OpenRouter once for all tracked models and store the result")

    report_cmd = sub.add_parser("report", help="Print the savings report as JSON")
    report_cmd.add_argument(
        "--no-live-fallback",
        action="store_true",
        help="Don't fall back to a live OpenRouter price lookup for models with no stored snapshot.",
    )

    sub.add_parser("uptime", help="Print the per-provider uptime/downtime summary as JSON")

    import_cmd = sub.add_parser("import-price-history", help="Backfill historical prices from a CSV file")
    import_cmd.add_argument("csv_path")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    store = Store(args.data_dir)
    client_kwargs = {"base_url": args.base_url} if args.base_url else {}
    client = OpenRouterClient(**client_kwargs)

    if args.command == "serve":
        serve(
            store,
            client,
            host=args.host,
            port=args.port,
            poll_interval_minutes=args.poll_interval_minutes,
        )
        return 0

    if args.command == "snapshot":
        _print(take_snapshot(store, client))
        return 0

    if args.command == "report":
        live_client = None if args.no_live_fallback else client
        report = compute_savings(store.usage.all(), store.price_snapshots.all(), live_client=live_client)
        _print(report.to_dict())
        return 0

    if args.command == "uptime":
        summaries = summarize_uptime(store.uptime_snapshots.all())
        _print([s.to_dict() for s in summaries])
        return 0

    if args.command == "import-price-history":
        try:
            snapshots = parse_price_history_csv(Path(args.csv_path))
        except CsvImportError as exc:
            parser.error(str(exc))
            return 2
        store.price_snapshots.replace_all(store.price_snapshots.all() + snapshots)
        _print({"imported": len(snapshots)})
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
