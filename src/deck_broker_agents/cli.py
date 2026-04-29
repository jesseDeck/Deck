"""CLI entrypoint for provisioning and running Deck agents."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from .deck_client import DeckClient
from .grocery_agents import GroceryProfileAgentManager
from .policy_agents import PolicyAgentManager


def _parse_source_overrides(raw_values: list[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in raw_values or []:
        if "=" not in item:
            raise ValueError(f"Invalid source override '{item}'. Expected format broker_system=url")
        key, value = item.split("=", maxsplit=1)
        overrides[key.strip().lower()] = value.strip()
    return overrides


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deck agent toolkit")
    parser.add_argument(
        "--registry-path",
        default=".deck/broker_agents.json",
        help="Path where created Deck resource IDs are stored.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Create broker source/agent/task records")
    bootstrap.add_argument(
        "--systems",
        default="acturis,open_gi,ssp",
        help="Comma-separated broker systems to bootstrap.",
    )
    bootstrap.add_argument(
        "--source-override",
        action="append",
        help="Optional source override in form broker_system=url",
    )

    create_cred = sub.add_parser("create-credential", help="Store broker username/password in Deck vault")
    create_cred.add_argument("--broker-system", required=True)
    create_cred.add_argument("--external-id", required=True)
    create_cred.add_argument("--username", required=True)
    create_cred.add_argument("--password", required=True)

    run = sub.add_parser("run", help="Run broker policy extraction task")
    run.add_argument("--broker-system", required=True)
    run.add_argument("--credential-id", required=True)
    run.add_argument("--client-reference", required=True)
    run.add_argument("--policy-number", action="append")
    run.add_argument("--include-inactive", action="store_true")
    run.add_argument("--as-of-date")
    run.add_argument("--session-id")
    run.add_argument("--idempotency-key")
    run.add_argument("--wait", action="store_true", help="Poll run until terminal state.")
    run.add_argument("--poll-seconds", type=int, default=5)
    run.add_argument("--timeout-seconds", type=int, default=600)

    interaction = sub.add_parser("submit-interaction", help="Submit MFA/security prompt input")
    interaction.add_argument("--task-run-id", required=True)
    interaction.add_argument(
        "--input-json",
        required=True,
        help='JSON object string, e.g. \'{"code":"123456"}\'',
    )

    get_run = sub.add_parser("get-run", help="Fetch task run details")
    get_run.add_argument("--task-run-id", required=True)
    get_run.add_argument("--include-storage", action="store_true")

    grocery_bootstrap = sub.add_parser(
        "grocery-bootstrap",
        help="Create Canadian grocery source/agent/task records",
    )
    grocery_bootstrap.add_argument(
        "--chains",
        default="loblaw,sobeys,metro",
        help="Comma-separated Canadian grocery chains to bootstrap.",
    )
    grocery_bootstrap.add_argument(
        "--source-override",
        action="append",
        help="Optional source override in form chain=url",
    )

    grocery_create_cred = sub.add_parser(
        "grocery-create-credential",
        help="Store grocery account username/password in Deck vault",
    )
    grocery_create_cred.add_argument("--chain", required=True)
    grocery_create_cred.add_argument("--external-id", required=True)
    grocery_create_cred.add_argument("--username", required=True)
    grocery_create_cred.add_argument("--password", required=True)

    grocery_run = sub.add_parser("grocery-run", help="Run grocery profile extraction task")
    grocery_run.add_argument("--chain", required=True)
    grocery_run.add_argument("--credential-id", required=True)
    grocery_run.add_argument("--profile-reference", required=True)
    grocery_run.add_argument("--include-order-history", action="store_true")
    grocery_run.add_argument("--order-history-limit", type=int)
    grocery_run.add_argument("--session-id")
    grocery_run.add_argument("--idempotency-key")
    grocery_run.add_argument("--wait", action="store_true", help="Poll run until terminal state.")
    grocery_run.add_argument("--poll-seconds", type=int, default=5)
    grocery_run.add_argument("--timeout-seconds", type=int, default=600)

    grocery_get_run = sub.add_parser("grocery-get-run", help="Fetch grocery task run details")
    grocery_get_run.add_argument("--task-run-id", required=True)
    grocery_get_run.add_argument("--include-storage", action="store_true")

    return parser


def _build_manager(registry_path: str) -> PolicyAgentManager:
    api_key = os.getenv("DECK_API_KEY", "")
    base_url = os.getenv("DECK_BASE_URL", "https://api.deck.co/v2")
    client = DeckClient(api_key=api_key, base_url=base_url)
    return PolicyAgentManager(client=client, registry_path=registry_path)


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    manager = _build_manager(args.registry_path)
    grocery_manager = GroceryProfileAgentManager(
        client=manager.client,
        registry_path=args.registry_path,
    )

    if args.command == "bootstrap":
        systems = [part.strip().lower() for part in args.systems.split(",") if part.strip()]
        overrides = _parse_source_overrides(args.source_override)
        registry = manager.bootstrap_many(systems, source_url_overrides=overrides)
        _print({k: vars(v) for k, v in registry.items()})
        return 0

    if args.command == "create-credential":
        credential = manager.create_user_credential(
            broker_system=args.broker_system,
            external_id=args.external_id,
            username=args.username,
            password=args.password,
        )
        _print(credential)
        return 0

    if args.command == "run":
        run = manager.run_policy_extraction(
            broker_system=args.broker_system,
            credential_id=args.credential_id,
            client_reference=args.client_reference,
            policy_numbers=args.policy_number,
            include_inactive=args.include_inactive,
            as_of_date=args.as_of_date,
            session_id=args.session_id,
            idempotency_key=args.idempotency_key,
        )
        if args.wait:
            terminal = manager.wait_for_terminal_status(
                run["id"],
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            )
            _print(terminal)
            return 0
        _print(run)
        return 0

    if args.command == "submit-interaction":
        payload = json.loads(args.input_json)
        response = manager.client.submit_interaction(
            task_run_id=args.task_run_id,
            interaction_input=payload,
        )
        _print(response)
        return 0

    if args.command == "get-run":
        run = manager.client.get_task_run(
            task_run_id=args.task_run_id,
            include_storage=args.include_storage,
        )
        _print(run)
        return 0

    if args.command == "grocery-bootstrap":
        chains = [part.strip().lower() for part in args.chains.split(",") if part.strip()]
        overrides = _parse_source_overrides(args.source_override)
        registry = grocery_manager.bootstrap_many(chains, source_url_overrides=overrides)
        _print({k: vars(v) for k, v in registry.items()})
        return 0

    if args.command == "grocery-create-credential":
        credential = grocery_manager.create_user_credential(
            chain=args.chain,
            external_id=args.external_id,
            username=args.username,
            password=args.password,
        )
        _print(credential)
        return 0

    if args.command == "grocery-run":
        run = grocery_manager.run_profile_extraction(
            chain=args.chain,
            credential_id=args.credential_id,
            profile_reference=args.profile_reference,
            include_order_history=args.include_order_history,
            order_history_limit=args.order_history_limit,
            session_id=args.session_id,
            idempotency_key=args.idempotency_key,
        )
        if args.wait:
            terminal = grocery_manager.wait_for_terminal_status(
                run["id"],
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            )
            _print(terminal)
            return 0
        _print(run)
        return 0

    if args.command == "grocery-get-run":
        run = grocery_manager.client.get_task_run(
            task_run_id=args.task_run_id,
            include_storage=args.include_storage,
        )
        _print(run)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
