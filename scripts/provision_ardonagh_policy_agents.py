#!/usr/bin/env python3
"""Provision Deck agent/task/sources for Ardonagh policy extraction."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deck_automation.client import DeckClient
from deck_automation.policy_task import INPUT_SCHEMA, OUTPUT_SCHEMA, TASK_NAME, TASK_PROMPT


DEFAULT_CONFIG = Path("config/ardonagh_bms_sources.json")
DEFAULT_OUTPUT = Path("outputs/provisioning-result.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to source configuration JSON.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write provisioning output JSON.",
    )
    parser.add_argument(
        "--agent-name",
        default="Ardonagh Policy Data Extractor",
        help="Deck agent display name.",
    )
    parser.add_argument(
        "--agent-description",
        default="Extract normalized policy data from Ardonagh-relevant broker management portals.",
        help="Deck agent description.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be provisioned without calling Deck API.",
    )
    parser.add_argument(
        "--skip-credentials",
        action="store_true",
        help="Do not create Deck credentials even when username/password env vars exist.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "systems" not in data or not isinstance(data["systems"], list):
        raise ValueError("Config must contain a top-level 'systems' array")
    return data


def env_credentials(system: dict[str, Any]) -> tuple[str | None, str | None]:
    credential_env = system.get("credential_env", {})
    username_key = credential_env.get("username")
    password_key = credential_env.get("password")
    username = os.environ.get(username_key) if username_key else None
    password = os.environ.get(password_key) if password_key else None
    return username, password


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    systems = config["systems"]

    result: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "dry_run": args.dry_run,
        "agent": None,
        "task": None,
        "systems": [],
    }

    if args.dry_run:
        result["agent"] = {"name": args.agent_name, "description": args.agent_description}
        result["task"] = {
            "name": TASK_NAME,
            "prompt": TASK_PROMPT,
            "input_schema": INPUT_SCHEMA,
            "output_schema": OUTPUT_SCHEMA,
        }

        for system in systems:
            username, password = env_credentials(system)
            result["systems"].append(
                {
                    "slug": system["slug"],
                    "source": {
                        "name": system["name"],
                        "type": "website",
                        "website": {"url": system["website_url"]},
                    },
                    "credential_planned": bool(username and password and not args.skip_credentials),
                }
            )
        print(json.dumps(result, indent=2))
        ensure_parent(args.output)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 0

    api_key = os.environ.get("DECK_API_KEY")
    if not api_key:
        raise RuntimeError("DECK_API_KEY must be set unless --dry-run is used")

    client = DeckClient(api_key=api_key)

    agent = client.create_agent(name=args.agent_name, description=args.agent_description)
    task = client.create_task(
        name=TASK_NAME,
        agent_id=agent["id"],
        prompt=TASK_PROMPT,
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
    )
    result["agent"] = {"id": agent["id"], "name": agent.get("name")}
    result["task"] = {"id": task["id"], "name": task.get("name"), "status": task.get("status")}

    for system in systems:
        source = client.create_source(name=system["name"], website_url=system["website_url"])
        username, password = env_credentials(system)
        credential = None

        if username and password and not args.skip_credentials:
            credential = client.create_credential(
                source_id=source["id"],
                username=username,
                password=password,
                external_id=f"ardonagh-{system['slug']}",
            )

        result["systems"].append(
            {
                "slug": system["slug"],
                "name": system["name"],
                "source_id": source["id"],
                "website_url": source.get("website", {}).get("url"),
                "credential_id": credential.get("id") if credential else None,
                "credential_status": credential.get("status") if credential else "not_created",
            }
        )

    ensure_parent(args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
