#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional


BASE_URL = "https://api.deck.co/v2"


def make_request(
    method: str,
    path: str,
    api_key: str,
    payload: Optional[Dict] = None,
    query: Optional[Dict[str, str]] = None,
) -> Dict:
    url = BASE_URL + path
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Cloudflare can reject Python's default user-agent in some environments.
            "User-Agent": "DeckBrokerBootstrap/1.0 (+https://docs.deck.co/)",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Deck API error {exc.code} on {method} {path}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error on {method} {path}: {exc.reason}") from exc


def list_resources(path: str, api_key: str) -> List[Dict]:
    items: List[Dict] = []
    cursor: Optional[str] = None

    while True:
        query = {"limit": "100"}
        if cursor:
            query["cursor"] = cursor
        response = make_request("GET", path, api_key, query=query)

        page = response.get("data")
        if page is None and isinstance(response, list):
            page = response
        if page is None:
            page = []
        if not isinstance(page, list):
            raise RuntimeError(f"Unexpected list response from {path}: {response}")

        items.extend(page)

        cursor = response.get("next_cursor") if isinstance(response, dict) else None
        if not cursor:
            break

    return items


def find_by_name(items: List[Dict], name: str) -> Optional[Dict]:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def ensure_source(
    broker_name: str, dashboard_url: str, api_key: str, existing_sources: List[Dict]
) -> Dict:
    source_name = f"{broker_name} Dashboard"
    existing = find_by_name(existing_sources, source_name)
    if existing:
        return existing

    created = make_request(
        "POST",
        "/sources",
        api_key,
        payload={
            "name": source_name,
            "type": "website",
            "website": {"url": dashboard_url},
        },
    )
    existing_sources.append(created)
    return created


def ensure_agent(broker_name: str, api_key: str, existing_agents: List[Dict]) -> Dict:
    agent_name = f"{broker_name} Portfolio Agent"
    existing = find_by_name(existing_agents, agent_name)
    if existing:
        return existing

    created = make_request(
        "POST",
        "/agents",
        api_key,
        payload={
            "name": agent_name,
            "description": (
                f"Automates {broker_name} dashboard workflows and returns "
                "structured portfolio data."
            ),
        },
    )
    existing_agents.append(created)
    return created


def load_brokers(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as fh:
        brokers = json.load(fh)
    if not isinstance(brokers, list):
        raise RuntimeError("Broker config must be a JSON array.")
    for broker in brokers:
        if not isinstance(broker, dict):
            raise RuntimeError("Each broker entry must be an object.")
        if "name" not in broker or "dashboard_url" not in broker:
            raise RuntimeError("Each broker entry must include name and dashboard_url.")
    return brokers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create/reuse Deck agents and sources for broker dashboards."
    )
    parser.add_argument(
        "--brokers-file",
        default="config/brokers.json",
        help="Path to broker JSON config file.",
    )
    parser.add_argument(
        "--out",
        default="deck_broker_resources.json",
        help="Where to write created/reused resource IDs.",
    )
    args = parser.parse_args()

    api_key = os.getenv("DECK_API_KEY")
    if not api_key:
        print("Missing DECK_API_KEY environment variable.", file=sys.stderr)
        return 1

    test = make_request("GET", "/test", api_key)
    environment = test.get("environment", "unknown")
    print(f"Deck API key verified. Environment: {environment}")

    brokers = load_brokers(args.brokers_file)
    existing_sources = list_resources("/sources", api_key)
    existing_agents = list_resources("/agents", api_key)

    results: List[Dict] = []
    for broker in brokers:
        name = broker["name"]
        url = broker["dashboard_url"]
        source = ensure_source(name, url, api_key, existing_sources)
        agent = ensure_agent(name, api_key, existing_agents)
        results.append(
            {
                "broker": name,
                "dashboard_url": url,
                "source_id": source.get("id"),
                "source_name": source.get("name"),
                "agent_id": agent.get("id"),
                "agent_name": agent.get("name"),
            }
        )
        print(
            f"- {name}: source={source.get('id')} ({source.get('name')}), "
            f"agent={agent.get('id')} ({agent.get('name')})"
        )

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"environment": environment, "resources": results}, fh, indent=2)
        fh.write("\n")

    print(f"\nWrote resource mapping to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
