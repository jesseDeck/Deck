# Deck Ardonagh Policy Extraction Toolkit

This repository contains a production-ready starter implementation for using
the Deck API to build computer-use agents and source connections that can
extract policy data from broker management systems that do not offer practical
self-serve APIs.

## What this includes

- A Deck API client using Python standard library (`urllib`).
- A provisioning script that creates:
  - an agent,
  - a reusable policy extraction task,
  - source connections for three Ardonagh-relevant systems.
- A task runner script that executes policy extraction and polls until
  completion.
- Research notes that document system selection and API-access rationale.

## Selected systems

The initial source set targets:

1. **Acturis**
2. **Open GI Transactor**
3. **RDT Landscape (legacy / GEO system)**

See `docs/ardonagh-bms-selection.md` for selection criteria and references.

## Prerequisites

- Python 3.10+
- A Deck API key with permission to create agents/tasks/sources/credentials.

Set environment variables:

```bash
export DECK_API_KEY="sk_live_..."
```

Optional per-source credential variables:

```bash
export ACTURIS_USERNAME="..."
export ACTURIS_PASSWORD="..."
export OPENGI_USERNAME="..."
export OPENGI_PASSWORD="..."
export RDT_LANDSCAPE_USERNAME="..."
export RDT_LANDSCAPE_PASSWORD="..."
```

## Provision agent + sources

Dry run (safe, no API calls):

```bash
python3 scripts/provision_ardonagh_policy_agents.py --dry-run
```

Provision in Deck:

```bash
python3 scripts/provision_ardonagh_policy_agents.py
```

The script writes the result to `outputs/provisioning-result.json`.

## Run extraction

```bash
python3 scripts/run_ardonagh_policy_extraction.py \
  --task-id task_xxx \
  --source-id src_xxx \
  --credential-id cred_xxx \
  --from-date 2026-01-01 \
  --to-date 2026-03-31
```

This writes the final run payload to `outputs/task-run-<run-id>.json`.

## Security notes

- Do not commit API keys or source credentials.
- Rotate any key that has been shared in plaintext.
- Use Deck credential vault (`/v2/credentials`) instead of storing passwords in
  local files.
