# Deck Broker Policy + Retail Pricing Agents

This repository provides a Python toolkit that provisions and runs [Deck](https://docs.deck.co) computer-use agents for:

1. **Client policy extraction** from UK/London broker systems
2. **Retail product pricing extraction** from e-commerce catalogs (including Ferguson faucets/sinks)
3. **Healthcare claims extraction** from US payer member portals and patient portals

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

## Healthcare claims agents

One agent per portal retrieves every claim (or billing statement, on provider portals) with billed amount,
claim ID, status, claim type, plan, plan paid amount, provider, service date, and patient/member
responsibility (with deductible / copay / coinsurance / not-covered breakdown when shown). EOB and
statement PDFs are captured to Deck storage with document extraction.

| Portal key | Source | Type | Default URL |
|---|---|---|---|
| `cigna` | Cigna | payer | https://my.cigna.com/ |
| `aetna` | Aetna | payer | https://health.aetna.com/ |
| `uhc` | UnitedHealthcare (myUHC) | payer | https://www.myuhc.com/ |
| `elevance` | Elevance Health (Anthem) | payer | https://www.anthem.com/login/ |
| `hcsc` | HCSC Blue Access for Members | payer | https://www.bcbsil.com/ (per state) |
| `highmark` | Highmark | payer | https://www.highmark.com/ |
| `mychart` | MyChart (Epic) | provider | https://www.mychart.org/ (per health system) |
| `athena` | athenaPatient | provider | https://myhealth.athenahealth.com/ |
| `mypatientportal` | MyPatientPortal | provider | https://www.mypatientportal.com/ (per practice) |
| `eclinicalworks` | eClinicalWorks (healow) | provider | https://healow.com/ (per practice) |

### 1) Bootstrap claims portals

```bash
python -m deck_broker_agents claims-bootstrap                     # all ten
python -m deck_broker_agents claims-bootstrap --portals cigna,uhc
```

IDs are written to `.deck/claims_agents.json`. Re-running skips portals already in the registry, so it
will not create duplicates. Per-organization portals (HCSC state plans, MyChart, MyPatientPortal,
eClinicalWorks) can be pointed at a specific login page; passing an override re-provisions that portal:

```bash
python -m deck_broker_agents claims-bootstrap --portals mychart \
  --source-override mychart=https://mychart.example-health.org/
```

### 2) Store the member's portal login

```bash
python -m deck_broker_agents claims-create-credential \
  --portal cigna --external-id member_123 \
  --username member@example.com --password "..."
```

### 3) Run claims extraction

```bash
python -m deck_broker_agents claims-run \
  --portal cigna --credential-id cred_abc123 \
  --service-date-from 2026-01-01 --service-date-to 2026-09-30 \
  --wait
```

Optional: `--member-name` (single dependent), `--claim-status` (repeatable), `--max-claims`, `--no-eobs`.
MFA prompts surface as `interaction_required`; answer them with `submit-interaction`.

Claims data is PHI. Only run these agents with the member's authorization, and handle outputs under
your HIPAA obligations.

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

## Development

Run tests:

```bash
pytest -q
```
