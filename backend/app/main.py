from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clusters, codebase, health, issues, tickets
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Local, evidence-grounded support ticket clustering and issue drafting.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(tickets.router)
    app.include_router(clusters.router)
    app.include_router(codebase.router)
    app.include_router(issues.router)

    return app


app = create_app()
