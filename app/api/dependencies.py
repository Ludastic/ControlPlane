from collections.abc import Generator
from functools import lru_cache

from app.core.settings import settings
from app.db.init_db import ensure_schema_up_to_date
from app.repositories.providers import build_sqlalchemy_repository_bundle
from app.services.control_plane_service import ControlPlaneService


@lru_cache(maxsize=1)
def get_memory_control_plane_service() -> ControlPlaneService:
    return ControlPlaneService()


def get_control_plane_service() -> Generator[ControlPlaneService, None, None]:
    if settings.storage_backend.lower() == "memory":
        yield get_memory_control_plane_service()
        return

    ensure_schema_up_to_date()
    bundle = build_sqlalchemy_repository_bundle()
    service = ControlPlaneService(repository_bundle=bundle, seed_demo_data=False)
    try:
        yield service
        bundle.commit()
    except Exception:
        bundle.rollback()
        raise
    finally:
        bundle.close()
