from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config_validation import validate_runtime_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.readiness import collect_readiness
from app.core.request_logging import configure_request_logging
from app.core.settings import settings


openapi_tags = [
    {"name": "system", "description": "Service health and readiness endpoints."},
    {"name": "agent", "description": "Endpoints used by workstation agents."},
    {"name": "admin-auth", "description": "Administrative authentication endpoints."},
    {"name": "admin", "description": "Administrative control plane endpoints."},
]


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    openapi_url=settings.openapi_url,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_tags=openapi_tags,
)
validate_runtime_settings()
register_exception_handlers(app)
configure_request_logging(app)
app.include_router(api_router)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def readinesscheck() -> JSONResponse:
    payload = collect_readiness()
    return JSONResponse(status_code=200 if payload["status"] == "ready" else 503, content=payload)
