# Deck documentation review notes

This implementation was based on these Deck docs pages:

- https://docs.deck.co/guides/quickstart.md
- https://docs.deck.co/concepts/tasks.md
- https://docs.deck.co/concepts/agents.md
- https://docs.deck.co/concepts/sources.md
- https://docs.deck.co/concepts/credentials.md
- https://docs.deck.co/api/using-the-api.md
- https://docs.deck.co/guides/interactions.md
- https://docs.deck.co/guides/storage.md

## API and behavior assumptions applied

1. **Base URL and auth**
   - Base URL is `https://api.deck.co/v2`
   - All requests use `Authorization: Bearer <DECK_API_KEY>`

2. **Resource provisioning flow**
   - Create source: `POST /sources`
   - Create agent: `POST /agents`
   - Create task: `POST /tasks`

3. **Credential vault**
   - User credentials are stored via `POST /credentials`
   - `auth_method` uses `username_password`

4. **Task execution**
   - Run task: `POST /tasks/{task_id}/run`
   - Poll run: `GET /task-runs/{task_run_id}`
   - Terminal statuses include `completed`, `failed`, and `interaction_required`

5. **Interactions**
   - Handle MFA/security prompts with `POST /task-runs/{run_id}/interaction`
   - Inputs are submitted as `{"input": {...}}`

6. **Storage and extraction**
   - Task config sets:
     - `storage.enabled = true`
     - `storage.extraction = true`
     - `storage.deduplication = true`
   - Storage list endpoint: `GET /task-runs/{run_id}/storage`

## Prompting choices from task guidance

Task prompt intentionally focuses on the goal ("retrieve normalized policy records and documents") rather than UI click-by-click instructions, matching Deck guidance to keep prompts source-agnostic.
