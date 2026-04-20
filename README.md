# Deck Broker Policy Agents

This repository provides a Python toolkit that provisions and runs [Deck](https://docs.deck.co) computer-use agents to extract **client policy data** from leading UK/London broker management systems, plus a Verizon billing workflow to switch the default payment card:

1. **Acturis**
2. **Open GI**
3. **SSP**

## What this project builds

Using Deck v2 APIs, the code can:

- create a **source** for each broker system
- create an **agent** for each broker system
- create a policy extraction **task** with normalized JSON output schema
- enable **storage + document extraction** for policy files (schedule, certificate, wording, endorsements)
- create per-user **credentials** in Deck Vault
- run task executions and poll until terminal status
- handle MFA/security prompts via interaction submission
- switch default payment card on Verizon (from cards already on file)

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

## Verizon payment-method switch workflow

The Verizon workflow creates a dedicated source/agent/task that signs in to Verizon, navigates to payment settings, and switches the default card to a target card already saved on the account.

### 1) Bootstrap Verizon resources

```bash
python -m deck_broker_agents bootstrap-verizon
```

This writes Deck resource IDs to `.deck/verizon_payment_agent.json`.

### 2) Store Verizon credential in Deck Vault

```bash
python -m deck_broker_agents create-verizon-credential \
  --external-id verizon_user_123 \
  --username your-verizon-login@example.com \
  --password "super-secret"
```

### 3) Run payment method switch

```bash
python -m deck_broker_agents run-verizon-switch \
  --credential-id cred_abc123 \
  --target-card-last4 4242 \
  --target-card-label "Personal Visa" \
  --confirm-switch \
  --wait
```

Optional flags for disambiguation and replay safety:

- `--billing-zip 10001`
- `--account-nickname "Family Plan"`
- `--idempotency-key verizon-switch-2026-04-20-001`

### 4) Submit interaction input (MFA/security question)

Use the same interaction command as other tasks:

```bash
python -m deck_broker_agents submit-interaction \
  --task-run-id trun_abc123 \
  --input-json '{"code":"123456"}'
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

## Security and compliance notes

- Only run this against systems and client records where you have explicit authorization.
- Credentials are stored in Deck Vault through the `credentials` endpoint.
- Do not hardcode secrets in source code or commit API keys.
- Rotate any secrets that were exposed in plaintext anywhere outside your secure secret manager.
- Use the Verizon payment switch workflow only on accounts where you are authorized to modify billing settings.

## Development

Run tests:

```bash
pytest -q
```
