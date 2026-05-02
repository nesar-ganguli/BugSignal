from fastapi import APIRouter

from app.config import get_settings
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    settings = get_settings()
    llm_client = LLMClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )
    ollama = await llm_client.health()

    return {
        "app": settings.app_name,
        "status": "ok",
        "ollama": ollama,
    }
