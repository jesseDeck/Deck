"""CLI entrypoint for provisioning and running Deck broker agents."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from .deck_client import DeckClient
from .policy_agents import PolicyAgentManager
from .youtube_history_agent import YouTubeHistoryAgentManager


def _parse_source_overrides(raw_values: list[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in raw_values or []:
        if "=" not in item:
            raise ValueError(f"Invalid source override '{item}'. Expected format broker_system=url")
        key, value = item.split("=", maxsplit=1)
        overrides[key.strip().lower()] = value.strip()
    return overrides


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deck broker policy extraction toolkit")
    parser.add_argument(
        "--registry-path",
        default=".deck/broker_agents.json",
        help="Path where created Deck resource IDs are stored.",
    )
    parser.add_argument(
        "--youtube-registry-path",
        default=".deck/youtube_history_agent.json",
        help="Path where YouTube Deck resource IDs are stored.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Create source/agent/task records")
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

    create_cred = sub.add_parser("create-credential", help="Store username/password in Deck vault")
    create_cred.add_argument("--broker-system", required=True)
    create_cred.add_argument("--external-id", required=True)
    create_cred.add_argument("--username", required=True)
    create_cred.add_argument("--password", required=True)

    run = sub.add_parser("run", help="Run policy extraction task")
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

    yt_bootstrap = sub.add_parser("youtube-bootstrap", help="Create source/agent/task for YouTube history")
    yt_bootstrap.add_argument("--source-url", default="https://www.youtube.com/")

    yt_create_cred = sub.add_parser(
        "youtube-create-credential",
        help="Store YouTube username/password in Deck vault",
    )
    yt_create_cred.add_argument("--external-id", required=True)
    yt_create_cred.add_argument("--username", required=True)
    yt_create_cred.add_argument("--password", required=True)

    yt_run = sub.add_parser("youtube-run", help="Run YouTube viewing history extraction")
    yt_run.add_argument("--credential-id", required=True)
    yt_run.add_argument("--start-date", help="YYYY-MM-DD (inclusive)")
    yt_run.add_argument("--end-date", help="YYYY-MM-DD (inclusive)")
    yt_run.add_argument("--days", type=int, default=7, help="Used when start-date is not provided.")
    yt_run.add_argument("--max-items", type=int, default=200)
    yt_run.add_argument("--session-id")
    yt_run.add_argument("--idempotency-key")
    yt_run.add_argument("--wait", action="store_true", help="Poll run until terminal state.")
    yt_run.add_argument("--poll-seconds", type=int, default=5)
    yt_run.add_argument("--timeout-seconds", type=int, default=600)

    return parser


def _build_manager(registry_path: str) -> PolicyAgentManager:
    api_key = os.getenv("DECK_API_KEY", "")
    base_url = os.getenv("DECK_BASE_URL", "https://api.deck.co/v2")
    client = DeckClient(api_key=api_key, base_url=base_url)
    return PolicyAgentManager(client=client, registry_path=registry_path)


def _build_youtube_manager(registry_path: str) -> YouTubeHistoryAgentManager:
    api_key = os.getenv("DECK_API_KEY", "")
    base_url = os.getenv("DECK_BASE_URL", "https://api.deck.co/v2")
    client = DeckClient(api_key=api_key, base_url=base_url)
    return YouTubeHistoryAgentManager(client=client, registry_path=registry_path)


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    manager = _build_manager(args.registry_path)
    youtube_manager = _build_youtube_manager(args.youtube_registry_path)

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

    if args.command == "youtube-bootstrap":
        record = youtube_manager.bootstrap(source_url=args.source_url)
        _print(vars(record))
        return 0

    if args.command == "youtube-create-credential":
        credential = youtube_manager.create_user_credential(
            external_id=args.external_id,
            username=args.username,
            password=args.password,
        )
        _print(credential)
        return 0

    if args.command == "youtube-run":
        run = youtube_manager.run_history_extraction(
            credential_id=args.credential_id,
            start_date=args.start_date,
            end_date=args.end_date,
            days=args.days,
            max_items=args.max_items,
            session_id=args.session_id,
            idempotency_key=args.idempotency_key,
        )
        if args.wait:
            terminal = youtube_manager.wait_for_terminal_status(
                run["id"],
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            )
            _print(terminal)
            return 0
        _print(run)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
