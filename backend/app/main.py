from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Depends

from app.api import auth, clusters, codebase, health, issues, projects, tickets, workflows
from app.config import get_settings
from app import models  # noqa: F401
from app.services.tenant_service import require_tenant_context


def create_app() -> FastAPI:
    settings = get_settings()
    frontend_origins = {
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
    app = FastAPI(
        title=settings.app_name,
        description="Local, evidence-grounded support ticket clustering and issue drafting.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(frontend_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    protected = [Depends(require_tenant_context)]
    app.include_router(tickets.router, dependencies=protected)
    app.include_router(clusters.router, dependencies=protected)
    app.include_router(codebase.router, dependencies=protected)
    app.include_router(issues.router, dependencies=protected)
    app.include_router(workflows.router, dependencies=protected)
    app.include_router(projects.router, dependencies=protected)

    return app


app = create_app()
