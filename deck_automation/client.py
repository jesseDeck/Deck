"""Minimal Deck API client for agent and task orchestration."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class DeckApiError(RuntimeError):
    """Raised when Deck returns a non-success response."""

    def __init__(self, status_code: int, message: str, response_body: Any | None = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Deck API error ({status_code}): {message}")


class DeckClient:
    """Thin wrapper around Deck REST endpoints used by this repository."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deck.co/v2",
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8").strip()
                    if not raw:
                        return {}
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                error_raw = exc.read().decode("utf-8", errors="replace")
                error_payload: dict[str, Any] | str = error_raw
                try:
                    error_payload = json.loads(error_raw)
                except json.JSONDecodeError:
                    pass

                if exc.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue

                if isinstance(error_payload, dict):
                    errors = error_payload.get("errors")
                    if isinstance(errors, list) and errors:
                        first_error = errors[0]
                        if isinstance(first_error, dict):
                            message = (
                                first_error.get("message")
                                or first_error.get("code")
                                or error_payload.get("title")
                                or "unknown error"
                            )
                        else:
                            message = str(first_error)
                    else:
                        message = (
                            error_payload.get("title")
                            or error_payload.get("detail")
                            or error_payload.get("message")
                            or "unknown error"
                        )
                else:
                    message = error_raw
                raise DeckApiError(exc.code, message, error_payload) from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise DeckApiError(0, f"Network error: {exc.reason}") from exc

        raise DeckApiError(0, "request retries exhausted")

    def create_agent(self, name: str, description: str) -> dict[str, Any]:
        return self._request("POST", "/agents", {"name": name, "description": description})

    def create_task(
        self,
        name: str,
        agent_id: str,
        prompt: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/tasks",
            {
                "name": name,
                "agent_id": agent_id,
                "prompt": prompt,
                "input_schema": input_schema,
                "output_schema": output_schema,
            },
        )

    def create_source(self, name: str, website_url: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/sources",
            {
                "name": name,
                "type": "website",
                "website": {"url": website_url},
            },
        )

    def create_credential(
        self,
        source_id: str,
        username: str,
        password: str,
        external_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": source_id,
            "auth_method": "username_password",
            "auth_credentials": {"username": username, "password": password},
        }
        if external_id:
            payload["external_id"] = external_id
        return self._request("POST", "/credentials", payload)

    def run_task(
        self,
        task_id: str,
        task_input: dict[str, Any],
        source_id: str | None = None,
        credential_id: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"input": task_input}
        if source_id:
            payload["source_id"] = source_id
        if credential_id:
            payload["credential_id"] = credential_id
        if session_id:
            payload["session_id"] = session_id
        if request_id:
            payload["request_id"] = request_id
        safe_task_id = urllib.parse.quote(task_id, safe="")
        return self._request("POST", f"/tasks/{safe_task_id}/run", payload)

    def get_task_run(self, run_id: str, include: str | None = None) -> dict[str, Any]:
        safe_run_id = urllib.parse.quote(run_id, safe="")
        path = f"/task-runs/{safe_run_id}"
        if include:
            path += f"?include={urllib.parse.quote(include, safe=',')}"
        return self._request("GET", path)

    def poll_task_run(
        self,
        run_id: str,
        poll_seconds: int = 5,
        timeout_seconds: int = 600,
        include: str | None = None,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        terminal_statuses = {"completed", "failed", "canceled"}
        pause_statuses = {"interaction_required", "review_required"}

        while True:
            run = self.get_task_run(run_id, include=include)
            status = run.get("status")
            if status in terminal_statuses or status in pause_statuses:
                return run
            if time.time() >= deadline:
                raise TimeoutError(f"Timed out waiting for task run {run_id}, last status={status}")
            time.sleep(poll_seconds)
