"""Minimal Deck API client for provisioning and running broker tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


class DeckAPIError(RuntimeError):
    """Raised when Deck API returns an error response."""

    def __init__(self, status_code: int, payload: dict[str, Any]):
        request_id = payload.get("request_id")
        message = payload.get("message") or payload.get("error") or "Deck API request failed"
        suffix = f" (request_id={request_id})" if request_id else ""
        super().__init__(f"{message}{suffix}")
        self.status_code = status_code
        self.payload = payload


@dataclass
class DeckClient:
    """Thin wrapper around Deck v2 endpoints used by this project."""

    api_key: str
    base_url: str = "https://api.deck.co/v2"
    timeout_seconds: int = 45

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        response = self._session.request(
            method=method,
            url=url,
            params=params,
            data=json.dumps(json_body) if json_body is not None else None,
            headers=headers or None,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            payload = self._try_json(response.text)
            raise DeckAPIError(response.status_code, payload)
        if not response.text:
            return {}
        return self._try_json(response.text)

    @staticmethod
    def _try_json(text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            return {"data": payload}
        except json.JSONDecodeError:
            return {"message": text}

    def test_key(self) -> dict[str, Any]:
        return self._request("GET", "/test")

    def create_agent(self, *, name: str, description: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/agents",
            json_body={"name": name, "description": description},
        )

    def create_source(self, *, name: str, website_url: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/sources",
            json_body={
                "name": name,
                "type": "website",
                "website": {"url": website_url},
            },
        )

    def create_task(
        self,
        *,
        agent_id: str,
        name: str,
        prompt: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        storage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "name": name,
            "prompt": prompt,
            "input_schema": input_schema,
            "output_schema": output_schema,
        }
        if storage is not None:
            payload["storage"] = storage
        return self._request("POST", "/tasks", json_body=payload)

    def create_credential(
        self,
        *,
        source_id: str,
        external_id: str,
        username: str,
        password: str,
        source_fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        auth_credentials: dict[str, Any] = {
            "username": username,
            "password": password,
        }
        if source_fields:
            auth_credentials["source_fields"] = source_fields
        return self._request(
            "POST",
            "/credentials",
            json_body={
                "source_id": source_id,
                "external_id": external_id,
                "auth_method": "username_password",
                "auth_credentials": auth_credentials,
            },
        )

    def run_task(
        self,
        *,
        task_id: str,
        credential_id: str,
        task_input: dict[str, Any],
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"credential_id": credential_id, "input": task_input}
        if session_id:
            payload["session_id"] = session_id
        return self._request(
            "POST",
            f"/tasks/{task_id}/run",
            json_body=payload,
            idempotency_key=idempotency_key,
        )

    def get_task_run(self, *, task_run_id: str, include_storage: bool = False) -> dict[str, Any]:
        params = {"include": "storage"} if include_storage else None
        return self._request("GET", f"/task-runs/{task_run_id}", params=params)

    def submit_interaction(self, *, task_run_id: str, interaction_input: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/task-runs/{task_run_id}/interaction",
            json_body={"input": interaction_input},
        )

    def list_storage(self, *, task_run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/task-runs/{task_run_id}/storage")
