from typing import Any

import httpx


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
