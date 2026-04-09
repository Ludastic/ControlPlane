from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import status

from app.core.errors import AppError
from app.repositories.in_memory import InMemoryRepository
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse, HostListResponse, HostResponse
from app.schemas.agent import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    ArtifactMetadataResponse,
    AgentInventoryResponse,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
    ExecutionEventsRequest,
    ExecutionEventsResponse,
    ExecutionRunCreateRequest,
    ExecutionRunCreateResponse,
    InventorySnapshot,
)
from app.schemas.admin import EffectivePoliciesResponse, ExecutionRunListResponse, ExecutionRunResponse, InventoryResponse
from app.schemas.admin import (
    GroupCreateRequest,
    GroupListResponse,
    GroupResponse,
    GroupUpdateRequest,
    PlaybookCreateRequest,
    PlaybookListResponse,
    PlaybookResponse,
    PlaybookUpdateRequest,
    PlaybookVersionCreateRequest,
    PlaybookVersionListResponse,
    PlaybookVersionResponse,
    PolicyAssignmentCreateRequest,
    PolicyAssignmentListResponse,
    PolicyAssignmentResponse,
    PolicyCreateRequest,
    PolicyListResponse,
    PolicyResourceCreateRequest,
    PolicyResourceListResponse,
    PolicyResourceResponse,
    PolicyResourceUpdateRequest,
    PolicyResponse,
    PolicyUpdateRequest,
)
from app.schemas.desired_state import ArtifactRef, DesiredResource, DesiredState


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class HostRecord:
    host_id: str
    agent_id: str
    token: str
    hostname: str
    fqdn: str
    status: str
    registered_at: datetime
    last_seen_at: datetime | None = None


class ControlPlaneService:
    def __init__(self) -> None:
        now = utcnow()
        self._repo = InMemoryRepository(now)
        demo_host = HostRecord(
            host_id="host_demo_01",
            agent_id="agent-demo-01",
            token="Bearer demo-agent-token",
            hostname="ws-dev-01",
            fqdn="ws-dev-01.company.local",
            status="online",
            registered_at=now,
            last_seen_at=now,
        )
        self._store_host(demo_host)
        self._repo.inventory_versions[demo_host.host_id] = 1
        self._repo.inventory_snapshots[demo_host.host_id] = {
            "collected_at": now.isoformat(),
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0-31-generic",
            "architecture": "x86_64",
            "hostname": demo_host.hostname,
            "fqdn": demo_host.fqdn,
            "ip_addresses": ["10.10.1.25"],
            "memory_mb": 16384,
            "disk": [{"mountpoint": "/", "size_gb": 512, "used_gb": 140}],
        }

    def _store_host(self, host: HostRecord) -> None:
        self._repo.hosts_by_id[host.host_id] = host
        self._repo.hosts_by_agent_id[host.agent_id] = host
        self._repo.hosts_by_token[host.token] = host

    def _require_agent(self, token: str | None) -> HostRecord:
        if token is None or token not in self._repo.hosts_by_token:
            raise AppError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_AGENT_TOKEN",
                message="Invalid agent token",
            )
        return self._repo.hosts_by_token[token]

    def register_agent(self, payload: AgentRegistrationRequest) -> AgentRegistrationResponse:
        now = utcnow()
        host = self._repo.hosts_by_agent_id.get(payload.agent_id)
        if host is None:
            host = HostRecord(
                host_id=f"host_{uuid4().hex[:12]}",
                agent_id=payload.agent_id,
                token=f"Bearer {uuid4().hex}",
                hostname=payload.hostname,
                fqdn=payload.fqdn,
                status="online",
                registered_at=now,
                last_seen_at=now,
            )
        else:
            host.hostname = payload.hostname
            host.fqdn = payload.fqdn
            host.status = "online"
            host.last_seen_at = now
        self._store_host(host)
        return AgentRegistrationResponse(
            host_id=host.host_id,
            agent_token=host.token.removeprefix("Bearer "),
            poll_interval_seconds=60,
            registered_at=host.registered_at,
        )

    def heartbeat(self, token: str | None, payload: AgentHeartbeatRequest) -> AgentHeartbeatResponse:
        host = self._require_agent(token)
        host.status = payload.status
        host.last_seen_at = utcnow()
        return AgentHeartbeatResponse(server_time=host.last_seen_at, poll_interval_seconds=60)

    def get_desired_state(self, token: str | None) -> DesiredState:
        host = self._require_agent(token)
        return self._build_desired_state(host.host_id)

    def update_inventory(self, token: str | None, payload: dict) -> AgentInventoryResponse:
        host = self._require_agent(token)
        snapshot = InventorySnapshot.model_validate(payload)
        version = self._inventory_versions.get(host.host_id, 0) + 1
        self._repo.inventory_versions[host.host_id] = version
        self._repo.inventory_snapshots[host.host_id] = snapshot.model_dump(mode="json")
        return AgentInventoryResponse(accepted=True, snapshot_version=version)

    def create_execution_run(
        self,
        token: str | None,
        payload: ExecutionRunCreateRequest,
    ) -> ExecutionRunCreateResponse:
        host = self._require_agent(token)
        run_id = f"run_{uuid4().hex[:12]}"
        self._repo.execution_runs[run_id] = {
            "host_id": host.host_id,
            "state_revision": payload.state_revision,
            "started_at": payload.started_at,
        }
        return ExecutionRunCreateResponse(run_id=run_id, accepted=True)

    def record_execution_events(
        self,
        token: str | None,
        run_id: str,
        payload: ExecutionEventsRequest,
    ) -> ExecutionEventsResponse:
        host = self._require_agent(token)
        run = self._repo.execution_runs.get(run_id)
        if run is None or run["host_id"] != host.host_id:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="EXECUTION_RUN_NOT_FOUND",
                message="Execution run not found",
            )
        run["events"] = [item.model_dump(mode="json") for item in payload.items]
        run["reported_at"] = payload.reported_at
        return ExecutionEventsResponse(accepted=True, processed_items=len(payload.items))

    def get_artifact_metadata(self, token: str | None, artifact_id: str) -> ArtifactMetadataResponse:
        self._require_agent(token)
        artifact = self._repo.artifacts.get(artifact_id)
        if artifact is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ARTIFACT_NOT_FOUND",
                message="Artifact not found",
            )
        return ArtifactMetadataResponse(
            artifact_id=artifact["artifact_id"],
            name=artifact["name"],
            version=artifact["version"],
            checksum=artifact["checksum"],
            content_type=artifact["content_type"],
            size_bytes=artifact["size_bytes"],
            download_url=f"/api/v1/agent/artifacts/{artifact_id}/download",
        )

    def download_artifact(self, token: str | None, artifact_id: str) -> dict:
        self._require_agent(token)
        artifact = self._repo.artifacts.get(artifact_id)
        if artifact is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ARTIFACT_NOT_FOUND",
                message="Artifact not found",
            )
        return artifact

    def admin_login(self, payload: AdminLoginRequest) -> AdminLoginResponse:
        if not payload.username or not payload.password:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CREDENTIALS_PAYLOAD",
                message="Username and password are required",
            )
        return AdminLoginResponse(
            access_token="admin-access-token",
            refresh_token="admin-refresh-token",
            token_type="Bearer",
            expires_in=3600,
        )

    def list_hosts(self) -> HostListResponse:
        items = [self._to_host_response(host) for host in self._repo.hosts_by_id.values()]
        return HostListResponse(items=items, total=len(items))

    def get_host(self, host_id: str) -> HostResponse:
        host = self._repo.hosts_by_id.get(host_id)
        if host is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        return self._to_host_response(host)

    def get_host_desired_state(self, host_id: str) -> DesiredState:
        if host_id not in self._repo.hosts_by_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        return self._build_desired_state(host_id)

    def get_host_inventory(self, host_id: str) -> InventoryResponse:
        if host_id not in self._repo.hosts_by_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        snapshot = self._repo.inventory_snapshots.get(host_id)
        version = self._repo.inventory_versions.get(host_id)
        if snapshot is None or version is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="INVENTORY_NOT_FOUND", message="Inventory not found")
        return InventoryResponse(host_id=host_id, snapshot_version=version, data=snapshot)

    def get_host_effective_policies(self, host_id: str) -> EffectivePoliciesResponse:
        if host_id not in self._repo.hosts_by_id:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        return EffectivePoliciesResponse(
            host_id=host_id,
            items=[
                {"policy_id": "pol_global_base", "scope": "global", "priority": 100},
                {"policy_id": "pol_group_eng", "scope": "group", "priority": 200},
            ],
        )

    def list_execution_runs(self) -> ExecutionRunListResponse:
        items = [
            ExecutionRunResponse(
                run_id=run_id,
                host_id=run["host_id"],
                state_revision=run["state_revision"],
                started_at=run["started_at"],
                events_count=len(run.get("events", [])),
            )
            for run_id, run in self._repo.execution_runs.items()
        ]
        return ExecutionRunListResponse(items=items, total=len(items))

    def list_groups(self) -> GroupListResponse:
        items = [GroupResponse(**group) for group in self._repo.groups.values()]
        return GroupListResponse(items=items, total=len(items))

    def create_group(self, payload: GroupCreateRequest) -> GroupResponse:
        group_id = f"grp_{uuid4().hex[:8]}"
        group = {"group_id": group_id, "name": payload.name, "description": payload.description}
        self._repo.groups[group_id] = group
        return GroupResponse(**group)

    def get_group(self, group_id: str) -> GroupResponse:
        group = self._repo.groups.get(group_id)
        if group is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found")
        return GroupResponse(**group)

    def update_group(self, group_id: str, payload: GroupUpdateRequest) -> GroupResponse:
        group = self._repo.groups.get(group_id)
        if group is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found")
        updates = payload.model_dump(exclude_none=True)
        group.update(updates)
        return GroupResponse(**group)

    def delete_group(self, group_id: str) -> None:
        if group_id not in self._repo.groups:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found")
        del self._repo.groups[group_id]

    def list_policies(self) -> PolicyListResponse:
        items = [PolicyResponse(**policy) for policy in self._repo.policies.values()]
        return PolicyListResponse(items=items, total=len(items))

    def create_policy(self, payload: PolicyCreateRequest) -> PolicyResponse:
        policy_id = f"pol_{uuid4().hex[:8]}"
        policy = {
            "policy_id": policy_id,
            "name": payload.name,
            "description": payload.description,
            "priority": payload.priority,
            "is_active": payload.is_active,
        }
        self._repo.policies[policy_id] = policy
        return PolicyResponse(**policy)

    def get_policy(self, policy_id: str) -> PolicyResponse:
        policy = self._repo.policies.get(policy_id)
        if policy is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        return PolicyResponse(**policy)

    def update_policy(self, policy_id: str, payload: PolicyUpdateRequest) -> PolicyResponse:
        policy = self._repo.policies.get(policy_id)
        if policy is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        updates = payload.model_dump(exclude_none=True)
        policy.update(updates)
        return PolicyResponse(**policy)

    def delete_policy(self, policy_id: str) -> None:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        self._repo.policies.pop(policy_id)
        for assignment_id in [key for key, value in self._repo.policy_assignments.items() if value["policy_id"] == policy_id]:
            self._repo.policy_assignments.pop(assignment_id)
        for resource_id in [key for key, value in self._repo.policy_resources.items() if value["policy_id"] == policy_id]:
            self._repo.policy_resources.pop(resource_id)

    def list_policy_assignments(self, policy_id: str) -> PolicyAssignmentListResponse:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        items = [
            PolicyAssignmentResponse(**assignment)
            for assignment in self._repo.policy_assignments.values()
            if assignment["policy_id"] == policy_id
        ]
        return PolicyAssignmentListResponse(items=items, total=len(items))

    def create_policy_assignment(
        self,
        policy_id: str,
        payload: PolicyAssignmentCreateRequest,
    ) -> PolicyAssignmentResponse:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        assignment_id = f"asg_{uuid4().hex[:8]}"
        assignment = {
            "assignment_id": assignment_id,
            "policy_id": policy_id,
            "target_type": payload.target_type,
            "target_id": payload.target_id,
        }
        self._repo.policy_assignments[assignment_id] = assignment
        return PolicyAssignmentResponse(**assignment)

    def delete_policy_assignment(self, policy_id: str, assignment_id: str) -> None:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        assignment = self._repo.policy_assignments.get(assignment_id)
        if assignment is None or assignment["policy_id"] != policy_id:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="POLICY_ASSIGNMENT_NOT_FOUND",
                message="Assignment not found",
            )
        self._repo.policy_assignments.pop(assignment_id)

    def list_playbooks(self) -> PlaybookListResponse:
        items = [PlaybookResponse(**playbook) for playbook in self._repo.playbooks.values()]
        return PlaybookListResponse(items=items, total=len(items))

    def create_playbook(self, payload: PlaybookCreateRequest) -> PlaybookResponse:
        playbook_id = f"pb_{uuid4().hex[:8]}"
        playbook = {
            "playbook_id": playbook_id,
            "name": payload.name,
            "description": payload.description,
        }
        self._repo.playbooks[playbook_id] = playbook
        return PlaybookResponse(**playbook)

    def get_playbook(self, playbook_id: str) -> PlaybookResponse:
        playbook = self._repo.playbooks.get(playbook_id)
        if playbook is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        return PlaybookResponse(**playbook)

    def update_playbook(self, playbook_id: str, payload: PlaybookUpdateRequest) -> PlaybookResponse:
        playbook = self._repo.playbooks.get(playbook_id)
        if playbook is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        updates = payload.model_dump(exclude_none=True)
        playbook.update(updates)
        return PlaybookResponse(**playbook)

    def delete_playbook(self, playbook_id: str) -> None:
        if playbook_id not in self._repo.playbooks:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        self._repo.playbooks.pop(playbook_id)

    def list_playbook_versions(self, playbook_id: str) -> PlaybookVersionListResponse:
        if playbook_id not in self._repo.playbooks:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        items = [
            PlaybookVersionResponse(
                artifact_id=artifact["artifact_id"],
                playbook_id=artifact["playbook_id"],
                version=artifact["version"],
                checksum=artifact["checksum"],
                immutable=True,
            )
            for artifact in self._repo.artifacts.values()
            if artifact["playbook_id"] == playbook_id
        ]
        return PlaybookVersionListResponse(items=items, total=len(items))

    def create_playbook_version(
        self,
        playbook_id: str,
        payload: PlaybookVersionCreateRequest,
    ) -> PlaybookVersionResponse:
        if playbook_id not in self._repo.playbooks:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        for artifact in self._repo.artifacts.values():
            if artifact["playbook_id"] == playbook_id and artifact["version"] == payload.version:
                raise AppError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="PLAYBOOK_VERSION_ALREADY_EXISTS",
                    message="Playbook version already exists",
                )
        artifact_id = f"art_{uuid4().hex[:10]}"
        artifact = {
            "artifact_id": artifact_id,
            "name": self._repo.playbooks[playbook_id]["name"],
            "playbook_id": playbook_id,
            "version": payload.version,
            "checksum": payload.checksum,
            "content_type": "application/gzip",
            "size_bytes": 0,
            "filename": f'{self._repo.playbooks[playbook_id]["name"]}-{payload.version}.tar.gz',
            "content": b"",
        }
        self._repo.artifacts[artifact_id] = artifact
        return PlaybookVersionResponse(
            artifact_id=artifact_id,
            playbook_id=playbook_id,
            version=payload.version,
            checksum=payload.checksum,
            immutable=True,
        )

    def list_policy_resources(self, policy_id: str) -> PolicyResourceListResponse:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        items = [
            PolicyResourceResponse(**resource)
            for resource in self._repo.policy_resources.values()
            if resource["policy_id"] == policy_id
        ]
        return PolicyResourceListResponse(items=items, total=len(items))

    def create_policy_resource(
        self,
        policy_id: str,
        payload: PolicyResourceCreateRequest,
    ) -> PolicyResourceResponse:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        if payload.playbook_id not in self._repo.playbooks:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="PLAYBOOK_NOT_FOUND", message="Playbook not found")
        if not self._playbook_version_exists(payload.playbook_id, payload.playbook_version):
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PLAYBOOK_VERSION_NOT_FOUND",
                message="Playbook version not found",
            )
        resource_id = f"res_{uuid4().hex[:8]}"
        resource = {
            "resource_id": resource_id,
            "policy_id": policy_id,
            "type": payload.type,
            "playbook_id": payload.playbook_id,
            "playbook_version": payload.playbook_version,
            "execution_order": payload.execution_order,
            "variables": payload.variables,
            "on_failure": payload.on_failure,
        }
        self._repo.policy_resources[resource_id] = resource
        return PolicyResourceResponse(**resource)

    def update_policy_resource(
        self,
        policy_id: str,
        resource_id: str,
        payload: PolicyResourceUpdateRequest,
    ) -> PolicyResourceResponse:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        resource = self._repo.policy_resources.get(resource_id)
        if resource is None or resource["policy_id"] != policy_id:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="POLICY_RESOURCE_NOT_FOUND",
                message="Policy resource not found",
            )
        updates = payload.model_dump(exclude_none=True)
        if "playbook_version" in updates and not self._playbook_version_exists(resource["playbook_id"], updates["playbook_version"]):
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PLAYBOOK_VERSION_NOT_FOUND",
                message="Playbook version not found",
            )
        resource.update(updates)
        return PolicyResourceResponse(**resource)

    def delete_policy_resource(self, policy_id: str, resource_id: str) -> None:
        if policy_id not in self._repo.policies:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="POLICY_NOT_FOUND", message="Policy not found")
        resource = self._repo.policy_resources.get(resource_id)
        if resource is None or resource["policy_id"] != policy_id:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="POLICY_RESOURCE_NOT_FOUND",
                message="Policy resource not found",
            )
        self._repo.policy_resources.pop(resource_id)

    def _playbook_version_exists(self, playbook_id: str, version: str) -> bool:
        return any(
            artifact["playbook_id"] == playbook_id and artifact["version"] == version
            for artifact in self._repo.artifacts.values()
        )

    def _to_host_response(self, host: HostRecord) -> HostResponse:
        return HostResponse(
            host_id=host.host_id,
            agent_id=host.agent_id,
            hostname=host.hostname,
            fqdn=host.fqdn,
            status=host.status,
            registered_at=host.registered_at,
            last_seen_at=host.last_seen_at,
        )

    def _build_desired_state(self, host_id: str) -> DesiredState:
        generated_at = utcnow()
        resources = [
            DesiredResource(
                resource_id="res_base",
                type="ansible_playbook",
                name="base-config",
                artifact=ArtifactRef(
                    artifact_id="art_base_01",
                    playbook_id="pb_base",
                    version="1.0.0",
                    checksum="sha256:abc123",
                    download_url="/api/v1/agent/artifacts/art_base_01/download",
                ),
                execution_order=10,
                variables={"timezone": "Europe/Moscow", "ntp_enabled": True},
                timeout_seconds=600,
                on_failure="stop",
            ),
            DesiredResource(
                resource_id="res_vpn",
                type="ansible_playbook",
                name="vpn-config",
                artifact=ArtifactRef(
                    artifact_id="art_vpn_01",
                    playbook_id="pb_vpn",
                    version="2.0.1",
                    checksum="sha256:def456",
                    download_url="/api/v1/agent/artifacts/art_vpn_01/download",
                ),
                execution_order=20,
                variables={"vpn_server": "vpn.company.local"},
                timeout_seconds=300,
                on_failure="continue",
            ),
        ]
        return DesiredState(
            host_id=host_id,
            revision=1,
            checksum="sha256:statechecksum123",
            generated_at=generated_at,
            resources=resources,
        )


control_plane_service = ControlPlaneService()
