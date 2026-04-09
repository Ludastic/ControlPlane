from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.errors import AppError
from app.core.settings import settings
from app.db.session import engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _build_alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def get_expected_schema_revision() -> str:
    script = ScriptDirectory.from_config(_build_alembic_config())
    return script.get_current_head()


def get_current_schema_revision() -> str | None:
    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        return None
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    return revision


def ensure_schema_up_to_date() -> None:
    current_revision = get_current_schema_revision()
    expected_revision = get_expected_schema_revision()
    if current_revision != expected_revision:
        raise AppError(
            status_code=503,
            code="DATABASE_SCHEMA_OUTDATED",
            message="Database schema is not up to date. Run 'alembic upgrade head'.",
            details={"current_revision": current_revision, "expected_revision": expected_revision},
        )
