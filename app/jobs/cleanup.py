from __future__ import annotations

from app.core.settings import settings
from app.repositories.providers import build_repository_bundle
from app.services.maintenance import MaintenanceService


def main() -> None:
    bundle = build_repository_bundle()
    service = MaintenanceService(bundle)
    try:
        summary = service.cleanup()
        if settings.storage_backend.lower() == "database":
            bundle.commit()
        print(summary.to_json())
    except Exception:
        if settings.storage_backend.lower() == "database":
            bundle.rollback()
        raise
    finally:
        if hasattr(bundle, "close"):
            bundle.close()


if __name__ == "__main__":
    main()
