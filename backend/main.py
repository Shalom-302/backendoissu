"""OISSU CONNECT application entry point.

The top-level FastAPI app is a thin parent that owns the lifespan and mounts
the API sub-application, which carries its own middleware and OpenAPI docs.

The sub-app is mounted at the ROOT rather than under ``/admin`` so the public
URLs match the technical design document exactly: ``/api/v1/auth/login``,
``/api/v1/athletes/me``, ``/api/v1/admin/athletes``... (doc §9). The ADMIN and
USER spaces are two role-guarded families of routes inside one API, not two
separately mounted applications: V1 has a single login screen for both.
"""
import logging

import uvicorn
from fastapi import FastAPI

from backend.core.conf import settings
from backend.core.registrar import register_app, register_init
from backend.app.api import admin_router

# The parent app owns the lifespan (DB tables, Redis, rate limiter) because
# Starlette does not run the lifespan of mounted sub-applications.
app = FastAPI(
    title=settings.FASTAPI_TITLE,
    lifespan=register_init,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Observability (opt-in). Enable with OBSERVABILITY_ENABLED=true and a valid
# OTLP_GRPC_ENDPOINT. Kept out of the lean core so the app boots without the
# OpenTelemetry/Prometheus stack installed.
if settings.OBSERVABILITY_ENABLED and settings.OTLP_GRPC_ENDPOINT:
    from backend.utils.prometheus import EndpointFilter, metrics, setting_otlp

    setting_otlp(app, settings.APP_NAME, settings.OTLP_GRPC_ENDPOINT)
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    app.add_route("/metrics", metrics)


@app.get("/", tags=["meta"], include_in_schema=False)
async def index() -> dict:
    """Signpost for anyone landing on the bare host.

    Declared before the mount below, so it wins over the sub-application for
    this exact path and nothing else.
    """
    return {
        "name": settings.FASTAPI_TITLE,
        "version": settings.FASTAPI_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": settings.FASTAPI_DOCS_URL,
        "health": "/health",
    }


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


# Mount the API. `/health` is declared above, so the parent still answers it.
app.mount("/", register_app(admin_router, "oissu connect"))


if __name__ == "__main__":
    # Handy for IDE debugging. In Docker the entrypoint runs uvicorn directly.
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "dev",
    )
