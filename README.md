# Deck Data Extraction Agents

This repository provides a Python toolkit that provisions and runs [Deck](https://docs.deck.co) computer-use agents for two extraction domains:

1. **UK/London broker policy data**
   - Acturis
   - Open GI
   - SSP
2. **Canadian grocery profile data**
   - Loblaw
   - Sobeys
   - Metro

## What this project builds

Using Deck v2 APIs, the code can:

- create a **source** for each broker system
- create an **agent** for each broker system
- create a policy extraction **task** with normalized JSON output schema
- enable **storage + document extraction** for policy files (schedule, certificate, wording, endorsements)
- create per-user **credentials** in Deck Vault
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

### UK broker policy workflow

### 1) Bootstrap all three systems

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

### Canadian grocery profile workflow

#### 1) Bootstrap top grocery chains

```bash
python -m deck_broker_agents grocery-bootstrap
```

This writes Deck resource IDs to `.deck/grocery_agents.json`.

You can override source URLs (useful for account-specific sign-in pages):

```bash
python -m deck_broker_agents grocery-bootstrap \
  --source-override loblaw=https://www.pcoptimum.ca/ \
  --source-override sobeys=https://www.sceneplus.ca/ \
  --source-override metro=https://www.metro.ca/
```

#### 2) Store user credential

```bash
python -m deck_broker_agents grocery-create-credential \
  --chain loblaw \
  --external-id customer_123 \
  --username customer@example.com \
  --password "super-secret"
```

#### 3) Run profile extraction

```bash
python -m deck_broker_agents grocery-run \
  --chain loblaw \
  --credential-id cred_abc123 \
  --customer-reference customer@example.com \
  --include-order-history \
  --max-orders 10 \
  --wait
```

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

Canadian grocery profile tasks return a normalized shape:

- `customer_reference`
- `grocery_chain`
- `profile`:
  - `first_name`
  - `last_name`
  - `email`
  - `phone`
  - `loyalty_id`
  - `account_status`
  - `preferred_store_id`
  - `preferred_store_name`
  - `points_balance`
  - `points_program_name`
  - `marketing_email_opt_in`
  - `marketing_sms_opt_in`
  - `addresses[]`
- `recent_orders[]`:
  - `order_id`
  - `order_date`
  - `order_total`
  - `currency`
  - `item_count`
  - `store_name`
- `retrieved_at`

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
