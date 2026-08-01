from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness_check() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    settings = get_settings()
    checks: dict[str, dict] = {}

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception:
        checks["database"] = {"status": "unavailable"}

    redis_client = Redis.from_url(
        settings.celery_broker_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        redis_client.ping()
        checks["redis"] = {"status": "ok"}
    except Exception:
        checks["redis"] = {"status": "unavailable"}
    finally:
        redis_client.close()

    llm_client = LLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)
    ollama = await llm_client.health()
    checks["ollama"] = {
        "status": "ok" if ollama.get("reachable") and ollama.get("model_available", True) else "unavailable",
        "model": settings.ollama_model,
    }

    ready = all(check["status"] == "ok" for check in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


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
