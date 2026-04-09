from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.core.settings import settings
from app.services.artifact_storage import artifact_storage


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CleanupSummary:
    orphan_artifact_files_deleted: int
    execution_runs_deleted: int
    audit_logs_deleted: int

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class MaintenanceService:
    def __init__(self, repo) -> None:
        self._repo = repo

    def cleanup(self, now: datetime | None = None) -> CleanupSummary:
        current_time = now or utcnow()
        execution_cutoff = current_time - timedelta(days=settings.execution_retention_days)
        audit_cutoff = current_time - timedelta(days=settings.audit_retention_days)

        referenced_paths = {
            artifact["storage_path"]
            for artifact in self._repo.artifacts.list_all()
        }
        deleted_files = 0
        for storage_path in artifact_storage.list_files():
            if storage_path in referenced_paths:
                continue
            if artifact_storage.delete(storage_path):
                deleted_files += 1

        deleted_runs = self._repo.execution.prune_before(execution_cutoff)
        deleted_audit_logs = self._repo.audit_logs.prune_before(audit_cutoff)

        return CleanupSummary(
            orphan_artifact_files_deleted=deleted_files,
            execution_runs_deleted=deleted_runs,
            audit_logs_deleted=deleted_audit_logs,
        )
