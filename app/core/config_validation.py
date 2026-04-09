from __future__ import annotations

from app.core.errors import AppError
from app.core.settings import Settings, settings


DEFAULT_ADMIN_SECRET = "dev-admin-secret"
DEFAULT_AGENT_REGISTRATION_TOKEN = "bootstrap-secret"


def validate_runtime_settings(current_settings: Settings | None = None) -> None:
    runtime_settings = current_settings or settings
    if runtime_settings.environment.lower() not in {"prod", "production"}:
        return

    if runtime_settings.admin_jwt_secret == DEFAULT_ADMIN_SECRET:
        raise AppError(
            status_code=503,
            code="INVALID_RUNTIME_CONFIGURATION",
            message="Production environment requires a non-default admin JWT secret.",
        )
    if runtime_settings.agent_registration_token == DEFAULT_AGENT_REGISTRATION_TOKEN:
        raise AppError(
            status_code=503,
            code="INVALID_RUNTIME_CONFIGURATION",
            message="Production environment requires a non-default agent registration token.",
        )
