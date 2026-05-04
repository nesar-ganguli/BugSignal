from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clusters, codebase, health, issues, tickets
from app.config import get_settings
from app.database import Base, engine, run_sqlite_migrations
from app import models  # noqa: F401


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
    app.include_router(tickets.router)
    app.include_router(clusters.router)
    app.include_router(codebase.router)
    app.include_router(issues.router)

    @app.on_event("startup")
    def create_database_tables() -> None:
        Base.metadata.create_all(bind=engine)
        run_sqlite_migrations()

    return app


app = create_app()
