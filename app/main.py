from fastapi import FastAPI

from app.api.router import api_router
from app.core.exception_handlers import register_exception_handlers
from app.core.settings import settings


app = FastAPI(title=settings.app_name, version=settings.app_version)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
