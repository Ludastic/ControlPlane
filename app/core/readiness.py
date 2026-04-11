from __future__ import annotations

from sqlalchemy import text

from app.core.settings import settings
from app.db.init_db import get_current_schema_revision, get_expected_schema_revision
from app.db.session import engine
from app.services.artifact_storage import artifact_storage


def _artifact_storage_check() -> dict:
    return artifact_storage.healthcheck()


def _database_check() -> dict:
    if settings.storage_backend.lower() != "database":
        return {"status": "skipped", "reason": "memory backend"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        current_revision = get_current_schema_revision()
        expected_revision = get_expected_schema_revision()
        if current_revision != expected_revision:
            return {
                "status": "failed",
                "current_revision": current_revision,
                "expected_revision": expected_revision,
            }
        return {
            "status": "ok",
            "current_revision": current_revision,
            "expected_revision": expected_revision,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def collect_readiness() -> dict:
    checks = {
        "database": _database_check(),
        "artifact_storage": _artifact_storage_check(),
    }
    ready = all(check["status"] in {"ok", "skipped"} for check in checks.values())
    return {"status": "ready" if ready else "not_ready", "checks": checks}
