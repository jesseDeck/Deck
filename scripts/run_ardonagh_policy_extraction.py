#!/usr/bin/env python3
"""Run a Deck policy extraction task and wait for completion."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deck_automation.client import DeckClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True, help="Deck task ID (task_...).")
    parser.add_argument("--source-id", help="Deck source ID (src_...).")
    parser.add_argument("--credential-id", help="Deck credential ID (cred_...).")
    parser.add_argument("--session-id", help="Optional Deck session ID to reuse (sess_...).")

    parser.add_argument("--from-date", required=True, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--to-date", required=True, help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--policy-number", help="Optional exact policy number filter.")
    parser.add_argument("--client-name", help="Optional customer/client name filter.")
    parser.add_argument("--include-cancelled", action="store_true", help="Include cancelled policies.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum policies to return.")

    parser.add_argument("--poll-seconds", type=int, default=5, help="Polling interval for run status.")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Max time to wait for completion.")
    parser.add_argument(
        "--include",
        default="input,storage,screenshots",
        help="Optional include parameter passed to GET /task-runs/{id}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory to write final task run payload JSON.",
    )
    return parser.parse_args()


def build_input(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "from_date": args.from_date,
        "to_date": args.to_date,
        "include_cancelled": args.include_cancelled,
        "limit": args.limit,
    }
    if args.policy_number:
        payload["policy_number"] = args.policy_number
    if args.client_name:
        payload["client_name"] = args.client_name
    return payload


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("DECK_API_KEY")
    if not api_key:
        raise RuntimeError("DECK_API_KEY is required")

    client = DeckClient(api_key=api_key)
    task_input = build_input(args)

    run = client.run_task(
        task_id=args.task_id,
        task_input=task_input,
        source_id=args.source_id,
        credential_id=args.credential_id,
        session_id=args.session_id,
    )

    run_id = run["id"]
    print(f"Created task run: {run_id} (status={run.get('status')})")

    final_run = client.poll_task_run(
        run_id=run_id,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
        include=args.include,
    )

    status = final_run.get("status")
    print(f"Final status: {status}")
    if status == "interaction_required":
        print("Task run requires user interaction (e.g., MFA).")
    elif status == "review_required":
        print("Task run requires human review.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"task-run-{run_id}.json"
    output_path.write_text(json.dumps(final_run, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
