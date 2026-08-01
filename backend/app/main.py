import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from fastapi import Depends

from app.api import auth, clusters, codebase, health, issues, projects, tickets, workflows
from app.config import get_settings
from app import models  # noqa: F401
from app.logging_config import configure_logging, request_id_context
from app.services.tenant_service import require_tenant_context


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("bugsignal.api")
    frontend_origins = set(settings.cors_origin_list)
    if settings.environment != "production":
        frontend_origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})
    if not settings.allowed_host_list:
        raise ValueError("ALLOWED_HOSTS must contain at least one host.")
    if settings.environment == "production" and "*" in frontend_origins:
        raise ValueError("Wildcard CORS origins are not allowed in production.")
    app = FastAPI(
        title=settings.app_name,
        description="Local, evidence-grounded support ticket clustering and issue drafting.",
        version="0.1.0",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(frontend_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID", "")
        request_id = incoming_id if incoming_id and len(incoming_id) <= 128 else str(uuid4())
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        started = perf_counter()
        content_length = request.headers.get("Content-Length")
        try:
            parsed_content_length = int(content_length) if content_length else 0
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        else:
            try:
                if parsed_content_length < 0:
                    response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
                elif parsed_content_length > settings.max_request_size_bytes:
                    response = JSONResponse(status_code=413, content={"detail": "Request body is too large."})
                else:
                    response = await call_next(request)
            except Exception:
                logger.exception(
                    "Unhandled request error",
                    extra={"method": request.method, "path": request.url.path},
                )
                raise
        try:
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if settings.environment == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            request_id_context.reset(token)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected server error occurred.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
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
