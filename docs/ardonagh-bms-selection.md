# Deck guide + API review and target-system selection

## 1) Deck documentation review (docs.deck.co)

The implementation in this repository is aligned to the following documented
Deck primitives and endpoints:

- **Core model:** agents, tasks, sources, credentials, task runs.
  - Concepts: <https://docs.deck.co/concepts/overview>
- **Provisioning flow:** create agent -> create task -> create source ->
  optional credential -> run task.
  - Quickstart: <https://docs.deck.co/guides/quickstart>
- **Endpoints used by this repo**
  - `POST /v2/agents`:
    <https://docs.deck.co/api-reference/agents/create-an-agent>
  - `POST /v2/tasks`:
    <https://docs.deck.co/api-reference/tasks/create-a-task>
  - `POST /v2/sources`:
    <https://docs.deck.co/api-reference/sources/create-a-source>
  - `POST /v2/credentials`:
    <https://docs.deck.co/api-reference/credentials/create-a-credential>
  - `POST /v2/tasks/{task_id}/run`:
    <https://docs.deck.co/api-reference/tasks/run-a-task>
  - `GET /v2/task-runs/{run_id}`:
    <https://docs.deck.co/api-reference/task-runs/retrieve-a-task-run>

Design choices in this repo intentionally follow Deck guidance on task prompts:
describe the **outcome** ("extract policy data"), not brittle click-by-click UI
steps, so the built-in agent harness can adapt to portal differences.

---

## 2) Top 3 Ardonagh-relevant broker systems without practical self-serve APIs

### A. Acturis

**Relevance**

- Ardonagh stated in its half-year 2019 results that all advisory sites were on
  Acturis:
  <https://www.ardonagh.com/announcements/2019/the-ardonagh-group-half-year-2019-results/>
- AutoRek's Ardonagh case announcement explicitly references Acturis as one of
  Ardonagh's key PAS data stores:
  <https://autorek.com/news/the-ardonagh-group-selects-autorek-to-drive-efficiency/>

**API gap rationale**

- Acturis has targeted partner APIs (for example the Aviva claims feed), but no
  broad public, self-serve API for generic broker policy extraction across all
  books and workflows:
  <https://www.acturis.com/blog/2024/12/13/aviva-and-acturis-launch-ground-breaking-broker-api-to-simplify-claims-process/>

### B. Open GI Transactor

**Relevance**

- AutoRek's Ardonagh announcement names OpenGI alongside Acturis as Ardonagh
  PAS systems for reconciliation and policy-level updates:
  <https://autorek.com/news/the-ardonagh-group-selects-autorek-to-drive-efficiency/>
- Midas Underwriting (part of Ardonagh) migration references an existing
  Transactor (Open GI) environment:
  <https://www.insurancedatasolutions.co.uk/latest-news/news/2022/january/data-migration-success-rdt-landscape-to-transactor/>

**API gap rationale**

- Open GI markets connectivity and integration capabilities but does not expose
  public self-service API contracts in the same way a commodity REST platform
  does, making direct build-and-run extraction projects depend on managed
  integrations:
  <https://www.opengi.co.uk/insurance-broker-software-solutions>

### C. RDT Landscape (legacy / GEO)

**Relevance**

- Midas Underwriting (Ardonagh group) documented migration from legacy RDT
  Landscape (GEO system) to Open GI Transactor, indicating historical policy
  data likely still needing extraction and normalization:
  <https://www.insurancedatasolutions.co.uk/latest-news/news/2022/january/data-migration-success-rdt-landscape-to-transactor/>

**API gap rationale**

- Legacy-system migration context and deployment style imply no practical modern
  self-serve API path for broad historical policy retrieval. Computer-use
  automation is the lower-friction pattern for extraction when direct APIs are
  unavailable.

---

## 3) Resulting implementation strategy

This repository provisions one normalized Deck task (`Extract Policy Data`) and
binds it to three source connections (Acturis, Open GI Transactor, RDT
Landscape). Credentials are optional and sourced from environment variables so
they are stored in Deck's credential vault, not in source control.
