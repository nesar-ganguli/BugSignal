from typing import Any
import json

import httpx


class LLMUnavailableError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMClient:
    """Single abstraction for local Ollama calls."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "reachable": False,
                "model": self.model,
                "error": f"Ollama is unavailable at {self.base_url}: {exc}",
            }

        data = response.json()
        models = [item.get("name") for item in data.get("models", [])]
        return {
            "reachable": True,
            "model": self.model,
            "model_available": self.model in models,
            "available_models": models,
        }

    async def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
        except httpx.RequestError as exc:
            raise LLMUnavailableError(
                f"Ollama is unavailable at {self.base_url}. Start Ollama and pull {self.model}."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMResponseError(
                f"Ollama returned {exc.response.status_code}: {exc.response.text}"
            ) from exc

        data = response.json()
        raw_response = data.get("response")
        if not isinstance(raw_response, str):
            raise LLMResponseError("Ollama response did not include a JSON text response.")

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise LLMResponseError("Ollama returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise LLMResponseError("Ollama JSON response must be an object.")
        return parsed
