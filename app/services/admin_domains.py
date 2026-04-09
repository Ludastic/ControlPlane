from __future__ import annotations

from uuid import uuid4

from fastapi import status

from app.core.errors import AppError
from app.repositories.in_memory import InMemoryRepository
from app.services.checksums import sha256_digest
from app.services.artifact_storage import artifact_storage
from app.services.composition import collect_applicable_policies
from app.schemas.admin import EffectivePoliciesResponse, ExecutionRunListResponse, ExecutionRunResponse, GroupCreateRequest, GroupListResponse, GroupResponse, GroupUpdateRequest, InventoryHistoryItem, InventoryHistoryResponse, InventoryResponse, PlaybookCreateRequest, PlaybookListResponse, PlaybookResponse, PlaybookUpdateRequest, PlaybookVersionCreateRequest, PlaybookVersionListResponse, PlaybookVersionResponse, PolicyAssignmentCreateRequest, PolicyAssignmentListResponse, PolicyAssignmentResponse, PolicyCreateRequest, PolicyListResponse, PolicyResourceCreateRequest, PolicyResourceListResponse, PolicyResourceResponse, PolicyResourceUpdateRequest, PolicyResponse, PolicyUpdateRequest


class AdminHostService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def get_host_inventory(self, host_id: str) -> InventoryResponse:
        if not self._repo.hosts.exists(host_id):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        snapshot = self._repo.inventory.get_snapshot(host_id)
        version = self._repo.inventory.get_version(host_id)
        if snapshot is None or version is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="INVENTORY_NOT_FOUND", message="Inventory not found")
        return InventoryResponse(host_id=host_id, snapshot_version=version, data=snapshot)

    def get_host_effective_policies(self, host_id: str) -> EffectivePoliciesResponse:
        if not self._repo.hosts.exists(host_id):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        return EffectivePoliciesResponse(host_id=host_id, items=collect_applicable_policies(self._repo, host_id))

    def get_host_inventory_history(self, host_id: str, limit: int | None = None) -> InventoryHistoryResponse:
        if not self._repo.hosts.exists(host_id):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        history = self._repo.inventory.list_history(host_id, limit=limit)
        items = [
            InventoryHistoryItem(
                snapshot_version=item["version"],
                collected_at=item["payload"]["collected_at"],
                data=item["payload"],
            )
            for item in history
        ]
        return InventoryHistoryResponse(host_id=host_id, items=items, total=len(items))

    def list_execution_runs(self, host_id: str | None = None, aggregate_status: str | None = None) -> ExecutionRunListResponse:
        items = []
        for run_id, run in self._repo.execution.list_all():
            status = self._aggregate_execution_status(run)
            if host_id is not None and run["host_id"] != host_id:
                continue
            if aggregate_status is not None and status != aggregate_status:
                continue
            items.append(
                ExecutionRunResponse(
                    run_id=run_id,
                    host_id=run["host_id"],
                    state_revision=run["state_revision"],
                    started_at=run["started_at"],
                    reported_at=run.get("reported_at"),
                    events_count=len(run.get("events", [])),
                    aggregate_status=status,
                )
            )
        return ExecutionRunListResponse(items=items, total=len(items))

    def _aggregate_execution_status(self, run: dict) -> str:
        events = run.get("events", [])
        if not events:
            return "running" if run.get("reported_at") is None else "pending"
        statuses = {event["status"] for event in events}
        if "failed" in statuses:
            return "failed"
        if "running" in statuses:
            return "running"
        if "pending" in statuses:
            return "pending"
        if statuses == {"skipped"}:
            return "skipped"
        if "cancelled" in statuses:
            return "cancelled"
        if "outdated" in statuses:
            return "outdated"
        return "success"


class GroupService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def list_groups(self) -> GroupListResponse:
        items = [GroupResponse(**group) for group in self._repo.groups.list_all()]
        return GroupListResponse(items=items, total=len(items))

    def create_group(self, payload: GroupCreateRequest) -> GroupResponse:
        group_id = f"grp_{uuid4().hex[:8]}"
        group = {"group_id": group_id, "name": payload.name, "description": payload.description}
        return GroupResponse(**self._repo.groups.save(group))

    def get_group(self, group_id: str) -> GroupResponse:
        group = self._repo.groups.get(group_id)
        if group is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found")
        return GroupResponse(**group)

    def update_group(self, group_id: str, payload: GroupUpdateRequest) -> GroupResponse:
        group = self._repo.groups.get(group_id)
        if group is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found")
        group.update(payload.model_dump(exclude_none=True))
        return GroupResponse(**group)

    def delete_group(self, group_id: str) -> None:
        group = self._repo.groups.get(group_id)
        if group is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found")
        self._repo.groups.delete(group)


class PolicyService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def list_policies(self) -> PolicyListResponse:
        items = [PolicyResponse(**policy) for policy in self._repo.policies.list_all()]
        return PolicyListResponse(items=items, total=len(items))

    def create_policy(self, payload: PolicyCreateRequest) -> PolicyResponse:
        policy_id = f"pol_{uuid4().hex[:8]}"
        policy = {"policy_id": policy_id, "name": payload.name, "description": payload.description, "priority": payload.priority, "is_active": payload.is_active}
        return PolicyResponse(**self._repo.policies.save(policy))

    def get_policy(self, policy_id: str) -> PolicyResponse:
        self._ensure_policy_exists(policy_id)
        return PolicyResponse(**self._repo.policies.get(policy_id))

    def update_policy(self, policy_id: str, payload: PolicyUpdateRequest) -> PolicyResponse:
        self._ensure_policy_exists(policy_id)
        policy = self._repo.policies.get(policy_id)
        policy.update(payload.model_dump(exclude_none=True))
        self._repo.policies.save(policy)
        return PolicyResponse(**policy)

    def delete_policy(self, policy_id: str) -> None:
        self._ensure_policy_exists(policy_id)
        self._repo.policies.delete(self._repo.policies.get(policy_id))
        for assignment in self._repo.policies.list_assignments(policy_id):
            self._repo.policies.delete_assignment(assignment["assignment_id"])
        for resource in self._repo.policies.list_resources(policy_id):
            self._repo.policies.delete_resource(resource["resource_id"])

    def list_policy_assignments(self, policy_id: str) -> PolicyAssignmentListResponse:
        self._ensure_policy_exists(policy_id)
        items = [PolicyAssignmentResponse(**assignment) for assignment in self._repo.policies.list_assignments(policy_id)]
        return PolicyAssignmentListResponse(items=items, total=len(items))

    def create_policy_assignment(self, policy_id: str, payload: PolicyAssignmentCreateRequest) -> PolicyAssignmentResponse:
        self._ensure_policy_exists(policy_id)
        assignment_id = f"asg_{uuid4().hex[:8]}"
        assignment = {"assignment_id": assignment_id, "policy_id": policy_id, "target_type": payload.target_type, "target_id": payload.target_id}
        return PolicyAssignmentResponse(**self._repo.policies.save_assignment(assignment))

    def delete_policy_assignment(self, policy_id: str, assignment_id: str) -> None:
        self._ensure_policy_exists(policy_id)
        assignment = self._repo.policies.get_assignment(assignment_id)
        if assignment is None or assignment["policy_id"] != policy_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_ASSIGNMENT_NOT_FOUND", message="Assignment not found")
        self._repo.policies.delete_assignment(assignment_id)

    def list_policy_resources(self, policy_id: str) -> PolicyResourceListResponse:
        self._ensure_policy_exists(policy_id)
        items = [PolicyResourceResponse(**resource) for resource in self._repo.policies.list_resources(policy_id)]
        return PolicyResourceListResponse(items=items, total=len(items))

    def create_policy_resource(self, policy_id: str, payload: PolicyResourceCreateRequest) -> PolicyResourceResponse:
        self._ensure_policy_exists(policy_id)
        if self._repo.playbooks.get(payload.playbook_id) is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        if not self._playbook_version_exists(payload.playbook_id, payload.playbook_version):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_VERSION_NOT_FOUND", message="Playbook version not found")
        resource_id = f"res_{uuid4().hex[:8]}"
        resource = {"resource_id": resource_id, "policy_id": policy_id, "type": payload.type, "playbook_id": payload.playbook_id, "playbook_version": payload.playbook_version, "execution_order": payload.execution_order, "variables": payload.variables, "on_failure": payload.on_failure}
        return PolicyResourceResponse(**self._repo.policies.save_resource(resource))

    def update_policy_resource(self, policy_id: str, resource_id: str, payload: PolicyResourceUpdateRequest) -> PolicyResourceResponse:
        self._ensure_policy_exists(policy_id)
        resource = self._repo.policies.get_resource(resource_id)
        if resource is None or resource["policy_id"] != policy_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_RESOURCE_NOT_FOUND", message="Policy resource not found")
        updates = payload.model_dump(exclude_none=True)
        if "playbook_version" in updates and not self._playbook_version_exists(resource["playbook_id"], updates["playbook_version"]):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_VERSION_NOT_FOUND", message="Playbook version not found")
        resource.update(updates)
        return PolicyResourceResponse(**resource)

    def delete_policy_resource(self, policy_id: str, resource_id: str) -> None:
        self._ensure_policy_exists(policy_id)
        resource = self._repo.policies.get_resource(resource_id)
        if resource is None or resource["policy_id"] != policy_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_RESOURCE_NOT_FOUND", message="Policy resource not found")
        self._repo.policies.delete_resource(resource_id)

    def _ensure_policy_exists(self, policy_id: str) -> None:
        if self._repo.policies.get(policy_id) is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")

    def _playbook_version_exists(self, playbook_id: str, version: str) -> bool:
        return self._repo.artifacts.get_by_playbook_version(playbook_id, version) is not None


class PlaybookService:
    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def list_playbooks(self) -> PlaybookListResponse:
        items = [PlaybookResponse(**playbook) for playbook in self._repo.playbooks.list_all()]
        return PlaybookListResponse(items=items, total=len(items))

    def create_playbook(self, payload: PlaybookCreateRequest) -> PlaybookResponse:
        playbook_id = f"pb_{uuid4().hex[:8]}"
        playbook = {"playbook_id": playbook_id, "name": payload.name, "description": payload.description}
        return PlaybookResponse(**self._repo.playbooks.save(playbook))

    def get_playbook(self, playbook_id: str) -> PlaybookResponse:
        self._ensure_playbook_exists(playbook_id)
        return PlaybookResponse(**self._repo.playbooks.get(playbook_id))

    def update_playbook(self, playbook_id: str, payload: PlaybookUpdateRequest) -> PlaybookResponse:
        self._ensure_playbook_exists(playbook_id)
        playbook = self._repo.playbooks.get(playbook_id)
        playbook.update(payload.model_dump(exclude_none=True))
        self._repo.playbooks.save(playbook)
        return PlaybookResponse(**playbook)

    def delete_playbook(self, playbook_id: str) -> None:
        self._ensure_playbook_exists(playbook_id)
        self._repo.playbooks.delete(self._repo.playbooks.get(playbook_id))

    def list_playbook_versions(self, playbook_id: str) -> PlaybookVersionListResponse:
        self._ensure_playbook_exists(playbook_id)
        items = [PlaybookVersionResponse(artifact_id=artifact["artifact_id"], playbook_id=artifact["playbook_id"], version=artifact["version"], checksum=artifact["checksum"], immutable=True) for artifact in self._repo.artifacts.list_by_playbook(playbook_id)]
        return PlaybookVersionListResponse(items=items, total=len(items))

    def create_playbook_version(self, playbook_id: str, payload: PlaybookVersionCreateRequest) -> PlaybookVersionResponse:
        self._ensure_playbook_exists(playbook_id)
        if self._repo.artifacts.get_by_playbook_version(playbook_id, payload.version) is not None:
            raise AppError(status_code=status.HTTP_409_CONFLICT, code="PLAYBOOK_VERSION_ALREADY_EXISTS", message="Playbook version already exists")
        artifact_id = f"art_{uuid4().hex[:10]}"
        playbook = self._repo.playbooks.get(playbook_id)
        filename = f'{playbook["name"]}-{payload.version}.tar.gz'
        storage_path = f"generated/{filename}"
        content = f"artifact:{playbook_id}:{payload.version}".encode("utf-8")
        calculated_checksum = sha256_digest(content)
        if payload.checksum != calculated_checksum:
            raise AppError(status_code=status.HTTP_409_CONFLICT, code="ARTIFACT_CHECKSUM_MISMATCH", message="Artifact checksum mismatch")
        artifact_storage.write_bytes(storage_path, content)
        artifact = {
            "artifact_id": artifact_id,
            "name": playbook["name"],
            "playbook_id": playbook_id,
            "version": payload.version,
            "checksum": payload.checksum,
            "content_type": "application/gzip",
            "size_bytes": len(content),
            "filename": filename,
            "storage_path": storage_path,
        }
        self._repo.artifacts.save(artifact)
        return PlaybookVersionResponse(artifact_id=artifact_id, playbook_id=playbook_id, version=payload.version, checksum=payload.checksum, immutable=True)

    def _ensure_playbook_exists(self, playbook_id: str) -> None:
        if self._repo.playbooks.get(playbook_id) is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
