from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.core.settings import settings
from app.db.base import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _build_alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migrations_upgrade_to_head_and_match_metadata(tmp_path) -> None:
    database_path = tmp_path / "migration_validation.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _build_alembic_config(database_url)
    original_database_url = settings.database_url

    settings.database_url = database_url
    try:
        command.upgrade(config, "head")

        script = ScriptDirectory.from_config(config)
        expected_revision = script.get_current_head()

        engine = create_engine(database_url, future=True)
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            metadata_table_names = set(Base.metadata.tables.keys())

            assert table_names == metadata_table_names | {"alembic_version"}

            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                diffs = compare_metadata(context, Base.metadata)
                current_revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()

            assert current_revision == expected_revision
            assert diffs == []
        finally:
            engine.dispose()
    finally:
        settings.database_url = original_database_url
