# Deck Broker Policy + Retail Pricing Agents

This repository provides a Python toolkit that provisions and runs [Deck](https://docs.deck.co) computer-use agents for:

1. **Client policy extraction** from UK/London broker systems
2. **Retail product pricing extraction** from e-commerce catalogs (including Ferguson faucets/sinks)

## Included policy connectors

The policy workflow supports these broker management systems:

1. **Acturis**
2. **Open GI**
3. **SSP**

## What this project builds

Using Deck v2 APIs, the code can:

- create a **source** for each target system/catalog
- create an **agent** for each use case
- create extraction **tasks** with normalized JSON output schema
- enable **storage + document extraction** for policy files (schedule, certificate, wording, endorsements)
- create per-user **credentials** in Deck Vault (`username_password` and `none`)
- run task executions and poll until terminal status
- handle MFA/security prompts via interaction submission

The implementation follows patterns described in:

- `https://docs.deck.co/guides/quickstart.md`
- `https://docs.deck.co/concepts/tasks.md`
- `https://docs.deck.co/concepts/credentials.md`
- `https://docs.deck.co/guides/interactions.md`
- `https://docs.deck.co/guides/storage.md`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure credentials

Set your Deck API key through environment variables.

```bash
export DECK_API_KEY="sk_live_..."
export DECK_BASE_URL="https://api.deck.co/v2"  # optional override
```

## CLI usage

### 1) Bootstrap all three policy systems

```bash
python -m deck_broker_agents bootstrap
```

This writes Deck resource IDs to `.deck/broker_agents.json`.

You can override source URLs (useful if you have tenant-specific login portals):

```bash
python -m deck_broker_agents bootstrap \
  --source-override acturis=https://broker-login.example.com/acturis \
  --source-override open_gi=https://broker-login.example.com/open-gi \
  --source-override ssp=https://broker-login.example.com/ssp
```

### 2) Store user credential

```bash
python -m deck_broker_agents create-credential \
  --broker-system acturis \
  --external-id client_123 \
  --username broker.user@example.com \
  --password "super-secret"
```

### 3) Run policy extraction

```bash
python -m deck_broker_agents run \
  --broker-system acturis \
  --credential-id cred_abc123 \
  --client-reference CL-100 \
  --policy-number POL-1 \
  --policy-number POL-2 \
  --wait
```

### 4) Submit interaction input (MFA/security question)

```bash
python -m deck_broker_agents submit-interaction \
  --task-run-id trun_abc123 \
  --input-json '{"code":"123456"}'
```

### 5) Retrieve task run details

```bash
python -m deck_broker_agents get-run \
  --task-run-id trun_abc123 \
  --include-storage
```

## Ferguson pricing agent

This project also includes a Deck task scaffold for extracting faucet and sink prices from Ferguson.

### 1) Bootstrap pricing catalog

```bash
python -m deck_broker_agents pricing-bootstrap --catalogs ferguson
```

This writes Deck resource IDs to `.deck/pricing_agents.json`.

### 2) (Optional) Create a no-auth credential link

For public catalog extraction, Deck supports `auth_method=none`. This can still be useful to link a user/external ID.

```bash
python -m deck_broker_agents pricing-create-credential \
  --catalog ferguson \
  --external-id buyer_123
```

### 3) Run pricing extraction for faucets and sinks

If no categories are specified, the task defaults to `faucets` and `sinks`.

```bash
python -m deck_broker_agents pricing-run \
  --catalog ferguson \
  --search-term kitchen \
  --search-term matte-black \
  --max-products-per-category 15 \
  --wait
```

You can also pass a credential ID if your catalog flow requires authentication:

```bash
python -m deck_broker_agents pricing-run \
  --catalog ferguson \
  --credential-id cred_abc123 \
  --category faucets \
  --category sinks \
  --wait
```

### 4) Pricing output schema

Each pricing run is configured to return:

- `catalog`
- `queried_categories[]`
- `products[]` with:
  - `category`
  - `name`
  - `brand`
  - `sku`
  - `price`
  - `currency`
  - `availability`
  - `product_url`
- `retrieved_at`

## Normalized extraction schema

Each task run is configured to return a broker-agnostic policy shape:

- `client_reference`
- `broker_system`
- `policies[]` with:
  - `policy_number`
  - `client_name`
  - `insurer_name`
  - `product_line`
  - `status`
  - `inception_date`
  - `expiry_date`
  - `premium_amount`
  - `currency`
  - `broker_reference`
  - `documents[]`

## OpenRouter savings & downtime calculator

A separate, unrelated tool also lives in this repo: `openrouter_savings`, a local
web app for figuring out how much you could save by routing through
[OpenRouter](https://openrouter.ai) instead of calling model providers directly,
and for tracking each provider's uptime over time.

You log what you actually paid a provider directly (model, provider, tokens,
cost) and tell it which models to track. It compares your real spend against
the cheapest OpenRouter-served provider for that same model, and separately
tracks per-provider uptime.

**Data limitation to know up front:** OpenRouter's public API only reports
*current* pricing and uptime -- there's no public API for historical
price-change or downtime logs (that view lives behind login at
[openrouter.ai/workspaces](https://openrouter.ai/workspaces)). So this tool
builds its own history going forward, by polling OpenRouter each time you run
`snapshot` (or run `serve --poll-interval-minutes`). You can backfill prices
from before you started tracking by importing a CSV (see below) -- for
example built from a community-maintained OpenRouter price-history dataset.

### Run it

```bash
python -m openrouter_savings serve
```

Then open <http://127.0.0.1:8787>. From there you can:

- Add usage entries (model, provider you actually used, tokens, cost)
- Track models so their price/uptime get polled ("Snapshot now", or pass
  `--poll-interval-minutes` to `serve` to poll automatically in the background)
- See total savings, a per-model/provider breakdown, a spend-over-time chart,
  and per-provider uptime/estimated downtime
- Backfill historical prices by pasting a CSV

All data is stored locally as JSON under `.openrouter_savings/` (override with
`--data-dir`). Nothing is sent anywhere except to OpenRouter's public,
unauthenticated catalog API.

### CLI

```bash
python -m openrouter_savings snapshot                    # poll tracked models once
python -m openrouter_savings report                      # print the savings report as JSON
python -m openrouter_savings uptime                      # print the uptime/downtime summary as JSON
python -m openrouter_savings import-price-history prices.csv
```

The import CSV needs a header of `model,provider,prompt_price,completion_price,effective_date`
(USD per token, ISO 8601 date).

### Tests

```bash
pytest -q tests/test_openrouter_*.py
```

## Security and compliance notes

- Only run this against systems and client records where you have explicit authorization.
- Credentials are stored in Deck Vault through the `credentials` endpoint.
- Do not hardcode secrets in source code or commit API keys.
- Rotate any secrets that were exposed in plaintext anywhere outside your secure secret manager.

## Development

Run tests:

```bash
pytest -q
```
