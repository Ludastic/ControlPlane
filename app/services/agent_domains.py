from __future__ import annotations

from fastapi import status

from app.core.errors import AppError
from app.core.settings import settings
from app.repositories.in_memory import InMemoryRepository
from app.services.checksums import verify_sha256
from app.services.artifact_storage import artifact_storage
from app.schemas.agent import ArtifactMetadataResponse, ExecutionEventsResponse, InventorySnapshot


class AgentArtifactService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def get_artifact_metadata(self, artifact_id: str) -> ArtifactMetadataResponse:
        artifact = self._repo.artifacts.get(artifact_id)
        if artifact is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="ARTIFACT_NOT_FOUND", message="Artifact not found")
        if not artifact_storage.exists(artifact["storage_path"]):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="ARTIFACT_CONTENT_NOT_FOUND", message="Artifact content not found")
        content = artifact_storage.read_bytes(artifact["storage_path"])
        if not verify_sha256(content, artifact["checksum"]):
            raise AppError(status_code=status.HTTP_409_CONFLICT, code="ARTIFACT_CHECKSUM_MISMATCH", message="Artifact checksum mismatch")
        return ArtifactMetadataResponse(
            artifact_id=artifact["artifact_id"],
            name=artifact["name"],
            version=artifact["version"],
            checksum=artifact["checksum"],
            content_type=artifact["content_type"],
            size_bytes=len(content),
            download_url=f"/api/v1/agent/artifacts/{artifact_id}/download",
        )

    def download_artifact(self, artifact_id: str) -> dict:
        artifact = self._repo.artifacts.get(artifact_id)
        if artifact is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="ARTIFACT_NOT_FOUND", message="Artifact not found")
        if not artifact_storage.exists(artifact["storage_path"]):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="ARTIFACT_CONTENT_NOT_FOUND", message="Artifact content not found")
        content = artifact_storage.read_bytes(artifact["storage_path"])
        if not verify_sha256(content, artifact["checksum"]):
            raise AppError(status_code=status.HTTP_409_CONFLICT, code="ARTIFACT_CHECKSUM_MISMATCH", message="Artifact checksum mismatch")
        return {
            "content": content,
            "content_type": artifact["content_type"],
            "filename": artifact["filename"],
        }


class AgentInventoryService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def update_inventory(self, host_id: str, payload: dict) -> int:
        snapshot = InventorySnapshot.model_validate(payload)
        version = (self._repo.inventory.get_version(host_id) or 0) + 1
        self._repo.inventory.save_snapshot(host_id, version, snapshot.model_dump(mode="json"))
        self._repo.inventory.prune_history(host_id, settings.inventory_retention_limit)
        return version


class AgentExecutionService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def record_execution_events(self, host_id: str, run_id: str, items: list, reported_at) -> ExecutionEventsResponse:
        run = self._repo.execution.get(run_id)
        if run is None or run["host_id"] != host_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="EXECUTION_RUN_NOT_FOUND", message="Execution run not found")
        existing_events = run.get("events", [])
        events_by_key = {
            self._event_key(event): event
            for event in existing_events
        }
        for item in items:
            event = item.model_dump(mode="json")
            events_by_key[self._event_key(event)] = event
        run["events"] = list(events_by_key.values())
        run["reported_at"] = reported_at
        self._repo.execution.save(run_id, run)
        return ExecutionEventsResponse(accepted=True, processed_items=len(items))

    def _event_key(self, event: dict) -> str:
        if event.get("event_id"):
            return f"id:{event['event_id']}"
        return "|".join(
            [
                event["resource_id"],
                event["artifact_id"],
                event["status"],
                str(event.get("started_at")),
                str(event.get("finished_at")),
                str(event.get("message")),
            ]
        )
