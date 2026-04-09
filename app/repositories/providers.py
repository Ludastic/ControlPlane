from __future__ import annotations

from datetime import datetime

from app.core.settings import settings
from app.db.session import SessionLocal
from app.repositories.in_memory import InMemoryRepository
from app.repositories.sqlalchemy_repositories import SqlAlchemyRepositoryBundle


def get_storage_backend_name() -> str:
    return settings.storage_backend.lower()


def build_repository_bundle():
    backend = get_storage_backend_name()
    if backend == "memory":
        return InMemoryRepository(datetime.utcnow())
    if backend == "database":
        return build_sqlalchemy_repository_bundle()
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


def build_sqlalchemy_repository_bundle() -> SqlAlchemyRepositoryBundle:
    session = SessionLocal()
    return SqlAlchemyRepositoryBundle(session)
