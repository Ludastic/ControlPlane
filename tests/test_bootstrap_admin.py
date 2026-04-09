from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.core.settings import settings
from app.models.user import User
from app.repositories.providers import ensure_bootstrap_admin
from app.repositories.sqlalchemy_repositories import SqlAlchemyRepositoryBundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_ensure_bootstrap_admin_creates_missing_user_and_is_idempotent(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "bootstrap_admin.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    original_database_url = settings.database_url
    original_username = settings.bootstrap_admin_username
    original_password = settings.bootstrap_admin_password
    settings.database_url = database_url
    settings.bootstrap_admin_username = "bootstrap_admin"
    settings.bootstrap_admin_password = "bootstrap_password"
    try:
        command.upgrade(_alembic_config(database_url), "head")

        engine = create_engine(database_url, future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        session = Session()
        try:
            bundle = SqlAlchemyRepositoryBundle(session)
            ensure_bootstrap_admin(bundle)
            session.commit()

            created_user = bundle.users.get_by_username("bootstrap_admin")
            assert created_user is not None

            existing_entity = session.get(User, created_user["user_id"])
            existing_entity.password_hash = hash_password("manually-changed")
            session.commit()

            ensure_bootstrap_admin(bundle)
            session.commit()

            preserved_user = bundle.users.get_by_username("bootstrap_admin")
            assert preserved_user is not None
            assert preserved_user["user_id"] == created_user["user_id"]
            assert preserved_user["password_hash"] == existing_entity.password_hash
        finally:
            session.close()
            engine.dispose()
    finally:
        settings.database_url = original_database_url
        settings.bootstrap_admin_username = original_username
        settings.bootstrap_admin_password = original_password
