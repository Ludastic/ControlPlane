from __future__ import annotations

from datetime import datetime
from hashlib import sha1

from app.core.settings import settings
from app.core.security import hash_password
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


def ensure_bootstrap_admin(bundle) -> None:
    username = settings.bootstrap_admin_username
    password = settings.bootstrap_admin_password
    if not username or not password:
        return
    existing_user = bundle.users.get_by_username(username)
    if existing_user is not None:
        return
    user_id = f"usr_bootstrap_{sha1(username.encode('utf-8')).hexdigest()[:12]}"
    bundle.users.save(
        {
            "user_id": user_id,
            "username": username,
            "password_hash": hash_password(password),
            "role": "admin",
            "is_active": True,
            "token_version": 1,
        }
    )
