# Deck Extraction Agents

This repository provides a Python toolkit that provisions and runs [Deck](https://docs.deck.co) computer-use agents for two extraction workflows:

1. **Broker policy extraction** from leading UK/London broker management systems:
   - Acturis
   - Open GI
   - SSP
2. **Athenahealth chart extraction** for patient medical records

## What this project builds

Using Deck v2 APIs, the code can:

- create a **source** for each system (broker platforms and Athenahealth)
- create an **agent** for each extraction workflow
- create extraction **tasks** with normalized JSON output schemas
- enable **storage + document extraction** for policy and chart documents
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

### Broker workflow

#### 1) Bootstrap all three broker systems

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

#### 2) Store user credential

```bash
python -m deck_broker_agents create-credential \
  --broker-system acturis \
  --external-id client_123 \
  --username broker.user@example.com \
  --password "super-secret"
```

#### 3) Run policy extraction

```bash
python -m deck_broker_agents run \
  --broker-system acturis \
  --credential-id cred_abc123 \
  --client-reference CL-100 \
  --policy-number POL-1 \
  --policy-number POL-2 \
  --wait
```

#### 4) Submit interaction input (MFA/security question)

```bash
python -m deck_broker_agents submit-interaction \
  --task-run-id trun_abc123 \
  --input-json '{"code":"123456"}'
```

#### 5) Retrieve task run details

```bash
python -m deck_broker_agents get-run \
  --task-run-id trun_abc123 \
  --include-storage
```

### Athenahealth workflow

#### 1) Bootstrap Athenahealth source/agent/task

```bash
python -m deck_broker_agents bootstrap-athena
```

This writes Deck resource IDs to `.deck/athena_agent.json`.

You can override the source URL if your organization uses a tenant-specific Athenahealth entry point:

```bash
python -m deck_broker_agents bootstrap-athena \
  --source-url https://athenanet.athenahealth.com/
```

#### 2) Store Athenahealth credential

```bash
python -m deck_broker_agents create-athena-credential \
  --external-id patient_user_123 \
  --username clinician.user@example.com \
  --password "super-secret" \
  --source-field department_id=77
```

Use `--source-field key=value` repeatedly for any required tenant/practice fields.

#### 3) Run Athenahealth medical record extraction

```bash
python -m deck_broker_agents run-athena \
  --credential-id cred_abc123 \
  --patient-reference MRN-12345 \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --section labs \
  --section medications \
  --wait
```

## Normalized extraction schemas

### Broker policy output

Each broker task run is configured to return a broker-agnostic policy shape:

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

### Athenahealth output

Athenahealth task runs return a normalized chart shape:

- `source_system`
- `patient`
  - `patient_reference`
  - `full_name`
  - `date_of_birth`
  - `sex`
- `records`
  - `encounters[]`
  - `problems[]`
  - `medications[]`
  - `allergies[]`
  - `labs[]`
  - `immunizations[]`
  - `vitals[]`
  - `documents[]`

## Security and compliance notes

- Only run this against systems and client records where you have explicit authorization.
- For Athenahealth workflows, ensure HIPAA and BAA obligations are satisfied before handling PHI.
- Credentials are stored in Deck Vault through the `credentials` endpoint.
- Do not hardcode secrets in source code or commit API keys.
- Rotate any secrets that were exposed in plaintext anywhere outside your secure secret manager.

## Development

Run tests:

```bash
pytest -q
```
