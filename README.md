# Deck Broker Agent Bootstrap

This repo includes a small bootstrap utility that creates (or reuses) Deck
resources for five major broker dashboards:

1. Charles Schwab
2. Fidelity Investments
3. Vanguard
4. E*TRADE
5. Interactive Brokers

For each broker, the script ensures:
- one `source` of type `website` for the login/dashboard URL
- one `agent` focused on portfolio/dashboard automation

## Files

- `config/brokers.json` — broker names and dashboard URLs
- `scripts/create_deck_broker_agents.py` — idempotent Deck API bootstrap script

## Usage

```bash
export DECK_API_KEY="sk_live_..."
python3 scripts/create_deck_broker_agents.py
```

By default the script writes created/reused IDs to:

```text
deck_broker_resources.json
```

You can provide custom paths:

```bash
python3 scripts/create_deck_broker_agents.py \
  --brokers-file config/brokers.json \
  --out /tmp/deck_broker_resources.json
```
