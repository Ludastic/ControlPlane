from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import status

from app.core.errors import AppError
from app.core.rbac import has_permission
from app.core.security import create_admin_token, decode_admin_token, extract_bearer_token, hash_agent_token, verify_password
from app.core.settings import settings
from app.repositories.in_memory import InMemoryRepository
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse, AdminMeResponse, AdminRefreshRequest, AdminTokenResponse, AgentTokenResponse, EffectivePoliciesResponse, ExecutionRunListResponse, GroupCreateRequest, GroupListResponse, GroupResponse, GroupUpdateRequest, HostListResponse, HostResponse, InventoryHistoryResponse, InventoryResponse, PlaybookCreateRequest, PlaybookListResponse, PlaybookResponse, PlaybookUpdateRequest, PlaybookVersionCreateRequest, PlaybookVersionListResponse, PlaybookVersionResponse, PolicyAssignmentCreateRequest, PolicyAssignmentListResponse, PolicyAssignmentResponse, PolicyCreateRequest, PolicyListResponse, PolicyResourceCreateRequest, PolicyResourceListResponse, PolicyResourceResponse, PolicyResourceUpdateRequest, PolicyResponse, PolicyUpdateRequest
from app.schemas.admin import AuditLogListResponse
from app.schemas.agent import AgentHeartbeatRequest, AgentHeartbeatResponse, AgentInventoryResponse, AgentRegistrationRequest, AgentRegistrationResponse, ArtifactMetadataResponse, ExecutionEventsRequest, ExecutionEventsResponse, ExecutionRunCreateRequest, ExecutionRunCreateResponse
from app.schemas.desired_state import ArtifactRef, DesiredResource, DesiredState
from app.services.composition import build_desired_state_payload
from app.services.admin_domains import AdminHostService, GroupService, PlaybookService, PolicyService
from app.services.agent_domains import AgentArtifactService, AgentExecutionService, AgentInventoryService
from app.services.artifact_storage import artifact_storage


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class HostRecord:
    host_id: str
    agent_id: str
    token: str | None
    hostname: str
    fqdn: str
    status: str
    registered_at: datetime
    last_seen_at: datetime | None = None


class ControlPlaneService:
    def __init__(self, repository_bundle: InMemoryRepository | None = None, seed_demo_data: bool = True) -> None:
        now = utcnow()
        self._repo = repository_bundle or InMemoryRepository(now)
        self._admin_host_service = AdminHostService(self._repo)
        self._group_service = GroupService(self._repo)
        self._policy_service = PolicyService(self._repo)
        self._playbook_service = PlaybookService(self._repo)
        self._agent_artifact_service = AgentArtifactService(self._repo)
        self._agent_inventory_service = AgentInventoryService(self._repo)
        self._agent_execution_service = AgentExecutionService(self._repo)

        if seed_demo_data:
            demo_host = HostRecord(host_id="host_demo_01", agent_id="agent-demo-01", token=hash_agent_token("demo-agent-token"), hostname="ws-dev-01", fqdn="ws-dev-01.company.local", status="online", registered_at=now, last_seen_at=now)
            self._store_host(demo_host)
            self._repo.groups.add_host_membership(demo_host.host_id, "grp_eng")
            for artifact in self._repo.artifacts.list_by_playbook("pb_base") + self._repo.artifacts.list_by_playbook("pb_vpn"):
                if "content" in artifact:
                    artifact_storage.ensure_bytes(artifact["storage_path"], artifact["content"])
            self._repo.inventory.save_snapshot(demo_host.host_id, 1, {
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
            })

    def _store_host(self, host: HostRecord) -> None:
        self._repo.hosts.save(host)

    def _host_id(self, host) -> str:
        return host.host_id if hasattr(host, "host_id") else host.id

    def _require_agent(self, token: str | None) -> HostRecord:
        bearer_token = extract_bearer_token(token, error_code="INVALID_AGENT_TOKEN", message="Invalid agent token")
        host = self._repo.hosts.get_by_token_hash(hash_agent_token(bearer_token))
        if host is None:
            raise AppError(status_code=status.HTTP_401_UNAUTHORIZED, code="INVALID_AGENT_TOKEN", message="Invalid agent token")
        return host

    def _issue_agent_token(self) -> tuple[str, str]:
        plain_token = token_urlsafe(24)
        return plain_token, hash_agent_token(plain_token)

    def _record_audit(
        self,
        *,
        actor: AdminMeResponse | dict,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        if isinstance(actor, AdminMeResponse):
            actor_user_id = actor.user_id
            actor_username = actor.username
        else:
            actor_user_id = actor["user_id"]
            actor_username = actor["username"]
        self._repo.audit_logs.save(
            {
                "audit_id": f"aud_{uuid4().hex[:12]}",
                "actor_user_id": actor_user_id,
                "actor_username": actor_username,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
                "created_at": utcnow(),
            }
        )

    def _require_admin(self, token: str | None, *, expected_type: str = "access", permission: str | None = None) -> dict:
        if token is None or not token.startswith("Bearer "):
            raise AppError(status_code=status.HTTP_401_UNAUTHORIZED, code="INVALID_ADMIN_TOKEN", message="Invalid admin token")
        claims = decode_admin_token(token.removeprefix("Bearer "), expected_type=expected_type)
        user = self._repo.users.get(claims["sub"])
        if user is None or not user["is_active"]:
            raise AppError(status_code=status.HTTP_401_UNAUTHORIZED, code="INVALID_ADMIN_TOKEN", message="Invalid admin token")
        if claims.get("ver") != user["token_version"]:
            raise AppError(status_code=status.HTTP_401_UNAUTHORIZED, code="INVALID_ADMIN_TOKEN", message="Invalid admin token")
        if permission is not None and not has_permission(user["role"], permission):
            raise AppError(status_code=status.HTTP_403_FORBIDDEN, code="ADMIN_FORBIDDEN", message="Admin access denied")
        return user

    def _issue_admin_tokens(self, user: dict) -> AdminTokenResponse:
        return AdminTokenResponse(
            access_token=create_admin_token(
                subject=user["user_id"],
                username=user["username"],
                role=user["role"],
                token_type="access",
                ttl_seconds=settings.admin_access_token_ttl_seconds,
                token_version=user["token_version"],
            ),
            refresh_token=create_admin_token(
                subject=user["user_id"],
                username=user["username"],
                role=user["role"],
                token_type="refresh",
                ttl_seconds=settings.admin_refresh_token_ttl_seconds,
                token_version=user["token_version"],
            ),
            token_type="Bearer",
            expires_in=settings.admin_access_token_ttl_seconds,
        )

    def register_agent(self, payload: AgentRegistrationRequest) -> AgentRegistrationResponse:
        if payload.registration_token != settings.agent_registration_token:
            raise AppError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_REGISTRATION_TOKEN",
                message="Invalid registration token",
            )
        now = utcnow()
        host = self._repo.hosts.get_by_agent_id(payload.agent_id)
        agent_token, token_hash = self._issue_agent_token()
        if host is None:
            host = HostRecord(host_id=f"host_{uuid4().hex[:12]}", agent_id=payload.agent_id, token=token_hash, hostname=payload.hostname, fqdn=payload.fqdn, status="online", registered_at=now, last_seen_at=now)
        else:
            host.hostname = payload.hostname
            host.fqdn = payload.fqdn
            host.status = "online"
            host.last_seen_at = now
            host.token = token_hash
        self._store_host(host)
        return AgentRegistrationResponse(
            host_id=self._host_id(host),
            agent_token=agent_token,
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
        return self._build_desired_state(self._host_id(host))

    def update_inventory(self, token: str | None, payload: dict) -> AgentInventoryResponse:
        host = self._require_agent(token)
        version = self._agent_inventory_service.update_inventory(self._host_id(host), payload)
        return AgentInventoryResponse(accepted=True, snapshot_version=version)

    def create_execution_run(self, token: str | None, payload: ExecutionRunCreateRequest) -> ExecutionRunCreateResponse:
        host = self._require_agent(token)
        run_id = f"run_{uuid4().hex[:12]}"
        self._repo.execution.save(run_id, {"host_id": self._host_id(host), "state_revision": payload.state_revision, "started_at": payload.started_at})
        return ExecutionRunCreateResponse(run_id=run_id, accepted=True)

    def record_execution_events(self, token: str | None, run_id: str, payload: ExecutionEventsRequest) -> ExecutionEventsResponse:
        host = self._require_agent(token)
        return self._agent_execution_service.record_execution_events(host_id=self._host_id(host), run_id=run_id, items=payload.items, reported_at=payload.reported_at)

    def get_artifact_metadata(self, token: str | None, artifact_id: str) -> ArtifactMetadataResponse:
        self._require_agent(token)
        return self._agent_artifact_service.get_artifact_metadata(artifact_id)

    def download_artifact(self, token: str | None, artifact_id: str) -> dict:
        self._require_agent(token)
        return self._agent_artifact_service.download_artifact(artifact_id)

    def admin_login(self, payload: AdminLoginRequest) -> AdminLoginResponse:
        if not payload.username or not payload.password:
            raise AppError(status_code=status.HTTP_400_BAD_REQUEST, code="INVALID_CREDENTIALS_PAYLOAD", message="Username and password are required")
        user = self._repo.users.get_by_username(payload.username)
        if user is None or not user["is_active"] or not verify_password(payload.password, user["password_hash"]):
            raise AppError(status_code=status.HTTP_401_UNAUTHORIZED, code="INVALID_ADMIN_CREDENTIALS", message="Invalid admin credentials")
        self._record_audit(actor=user, action="admin.login", entity_type="auth", entity_id=user["user_id"])
        return AdminLoginResponse(**self._issue_admin_tokens(user).model_dump())

    def admin_refresh(self, payload: AdminRefreshRequest) -> AdminTokenResponse:
        user = self._require_admin(f"Bearer {payload.refresh_token}", expected_type="refresh")
        return self._issue_admin_tokens(user)

    def admin_logout(self, token: str | None) -> None:
        user = self._require_admin(token, expected_type="access")
        updated_user = {
            **user,
            "token_version": user["token_version"] + 1,
        }
        self._repo.users.save(updated_user)
        self._record_audit(actor=user, action="admin.logout", entity_type="auth", entity_id=user["user_id"])

    def get_admin_me(self, token: str | None) -> AdminMeResponse:
        user = self._require_admin(token, expected_type="access")
        return AdminMeResponse(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            is_active=user["is_active"],
        )

    def require_admin_permission(self, token: str | None, permission: str) -> AdminMeResponse:
        user = self._require_admin(token, expected_type="access", permission=permission)
        return AdminMeResponse(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            is_active=user["is_active"],
        )

    def rotate_host_agent_token(self, host_id: str, actor: AdminMeResponse) -> AgentTokenResponse:
        host = self._repo.hosts.get(host_id)
        if host is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        agent_token, token_hash = self._issue_agent_token()
        if hasattr(host, "token"):
            host.token = token_hash
        else:
            host.agent_token_hash = token_hash
        self._repo.hosts.save(host)
        self._record_audit(actor=actor, action="host.agent_token.rotate", entity_type="host", entity_id=host_id)
        return AgentTokenResponse(host_id=host_id, agent_token=agent_token, rotated_at=utcnow())

    def revoke_host_agent_token(self, host_id: str, actor: AdminMeResponse) -> None:
        host = self._repo.hosts.get(host_id)
        if host is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        if hasattr(host, "token"):
            host.token = None
        else:
            host.agent_token_hash = None
        self._repo.hosts.save(host)
        self._record_audit(actor=actor, action="host.agent_token.revoke", entity_type="host", entity_id=host_id)

    def list_hosts(self) -> HostListResponse:
        items = [self._to_host_response(host) for host in self._repo.hosts.list_all()]
        return HostListResponse(items=items, total=len(items))

    def get_host(self, host_id: str) -> HostResponse:
        host = self._repo.hosts.get(host_id)
        if host is None:
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        return self._to_host_response(host)

    def get_host_desired_state(self, host_id: str) -> DesiredState:
        if not self._repo.hosts.exists(host_id):
            raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="HOST_NOT_FOUND", message="Host not found")
        return self._build_desired_state(host_id)

    def get_host_inventory(self, host_id: str) -> InventoryResponse:
        return self._admin_host_service.get_host_inventory(host_id)

    def get_host_inventory_history(self, host_id: str, limit: int | None = None) -> InventoryHistoryResponse:
        return self._admin_host_service.get_host_inventory_history(host_id, limit=limit)

    def get_host_effective_policies(self, host_id: str) -> EffectivePoliciesResponse:
        return self._admin_host_service.get_host_effective_policies(host_id)

    def list_execution_runs(self, host_id: str | None = None, aggregate_status: str | None = None) -> ExecutionRunListResponse:
        return self._admin_host_service.list_execution_runs(host_id=host_id, aggregate_status=aggregate_status)

    def list_audit_log(
        self,
        *,
        user_id: str | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        limit: int | None = None,
    ) -> AuditLogListResponse:
        items = self._repo.audit_logs.list_all(user_id=user_id, entity_type=entity_type, action=action, limit=limit)
        return AuditLogListResponse(items=items, total=len(items))

    def list_groups(self) -> GroupListResponse:
        return self._group_service.list_groups()

    def create_group(self, payload: GroupCreateRequest, actor: AdminMeResponse) -> GroupResponse:
        group = self._group_service.create_group(payload)
        self._record_audit(actor=actor, action="group.create", entity_type="group", entity_id=group.group_id)
        return group

    def get_group(self, group_id: str) -> GroupResponse:
        return self._group_service.get_group(group_id)

    def update_group(self, group_id: str, payload: GroupUpdateRequest, actor: AdminMeResponse) -> GroupResponse:
        group = self._group_service.update_group(group_id, payload)
        self._record_audit(actor=actor, action="group.update", entity_type="group", entity_id=group.group_id)
        return group

    def delete_group(self, group_id: str, actor: AdminMeResponse) -> None:
        self._group_service.delete_group(group_id)
        self._record_audit(actor=actor, action="group.delete", entity_type="group", entity_id=group_id)

    def list_policies(self) -> PolicyListResponse:
        return self._policy_service.list_policies()

    def create_policy(self, payload: PolicyCreateRequest, actor: AdminMeResponse) -> PolicyResponse:
        policy = self._policy_service.create_policy(payload)
        self._record_audit(actor=actor, action="policy.create", entity_type="policy", entity_id=policy.policy_id)
        return policy

    def get_policy(self, policy_id: str) -> PolicyResponse:
        return self._policy_service.get_policy(policy_id)

    def update_policy(self, policy_id: str, payload: PolicyUpdateRequest, actor: AdminMeResponse) -> PolicyResponse:
        policy = self._policy_service.update_policy(policy_id, payload)
        self._record_audit(actor=actor, action="policy.update", entity_type="policy", entity_id=policy.policy_id)
        return policy

    def delete_policy(self, policy_id: str, actor: AdminMeResponse) -> None:
        self._policy_service.delete_policy(policy_id)
        self._record_audit(actor=actor, action="policy.delete", entity_type="policy", entity_id=policy_id)

    def list_policy_assignments(self, policy_id: str) -> PolicyAssignmentListResponse:
        return self._policy_service.list_policy_assignments(policy_id)

    def create_policy_assignment(self, policy_id: str, payload: PolicyAssignmentCreateRequest, actor: AdminMeResponse) -> PolicyAssignmentResponse:
        assignment = self._policy_service.create_policy_assignment(policy_id, payload)
        self._record_audit(actor=actor, action="policy.assignment.create", entity_type="policy_assignment", entity_id=assignment.assignment_id, details={"policy_id": policy_id})
        return assignment

    def delete_policy_assignment(self, policy_id: str, assignment_id: str, actor: AdminMeResponse) -> None:
        self._policy_service.delete_policy_assignment(policy_id, assignment_id)
        self._record_audit(actor=actor, action="policy.assignment.delete", entity_type="policy_assignment", entity_id=assignment_id, details={"policy_id": policy_id})

    def list_playbooks(self) -> PlaybookListResponse:
        return self._playbook_service.list_playbooks()

    def create_playbook(self, payload: PlaybookCreateRequest, actor: AdminMeResponse) -> PlaybookResponse:
        playbook = self._playbook_service.create_playbook(payload)
        self._record_audit(actor=actor, action="playbook.create", entity_type="playbook", entity_id=playbook.playbook_id)
        return playbook

    def get_playbook(self, playbook_id: str) -> PlaybookResponse:
        return self._playbook_service.get_playbook(playbook_id)

    def update_playbook(self, playbook_id: str, payload: PlaybookUpdateRequest, actor: AdminMeResponse) -> PlaybookResponse:
        playbook = self._playbook_service.update_playbook(playbook_id, payload)
        self._record_audit(actor=actor, action="playbook.update", entity_type="playbook", entity_id=playbook.playbook_id)
        return playbook

    def delete_playbook(self, playbook_id: str, actor: AdminMeResponse) -> None:
        self._playbook_service.delete_playbook(playbook_id)
        self._record_audit(actor=actor, action="playbook.delete", entity_type="playbook", entity_id=playbook_id)

    def list_playbook_versions(self, playbook_id: str) -> PlaybookVersionListResponse:
        return self._playbook_service.list_playbook_versions(playbook_id)

    def create_playbook_version(self, playbook_id: str, payload: PlaybookVersionCreateRequest, actor: AdminMeResponse) -> PlaybookVersionResponse:
        version = self._playbook_service.create_playbook_version(playbook_id, payload)
        self._record_audit(actor=actor, action="playbook.version.create", entity_type="artifact", entity_id=version.artifact_id, details={"playbook_id": playbook_id, "version": version.version})
        return version

    def list_policy_resources(self, policy_id: str) -> PolicyResourceListResponse:
        return self._policy_service.list_policy_resources(policy_id)

    def create_policy_resource(self, policy_id: str, payload: PolicyResourceCreateRequest, actor: AdminMeResponse) -> PolicyResourceResponse:
        resource = self._policy_service.create_policy_resource(policy_id, payload)
        self._record_audit(actor=actor, action="policy.resource.create", entity_type="policy_resource", entity_id=resource.resource_id, details={"policy_id": policy_id})
        return resource

    def update_policy_resource(self, policy_id: str, resource_id: str, payload: PolicyResourceUpdateRequest, actor: AdminMeResponse) -> PolicyResourceResponse:
        resource = self._policy_service.update_policy_resource(policy_id, resource_id, payload)
        self._record_audit(actor=actor, action="policy.resource.update", entity_type="policy_resource", entity_id=resource.resource_id, details={"policy_id": policy_id})
        return resource

    def delete_policy_resource(self, policy_id: str, resource_id: str, actor: AdminMeResponse) -> None:
        self._policy_service.delete_policy_resource(policy_id, resource_id)
        self._record_audit(actor=actor, action="policy.resource.delete", entity_type="policy_resource", entity_id=resource_id, details={"policy_id": policy_id})

    def _to_host_response(self, host: HostRecord) -> HostResponse:
        return HostResponse(
            host_id=self._host_id(host),
            agent_id=host.agent_id,
            hostname=host.hostname,
            fqdn=host.fqdn,
            status=host.status,
            registered_at=host.registered_at,
            last_seen_at=host.last_seen_at,
        )

    def _build_desired_state(self, host_id: str) -> DesiredState:
        payload = build_desired_state_payload(self._repo, host_id)
        resources = [
            DesiredResource(
                resource_id=item["resource_id"],
                type=item["type"],
                name=item["name"],
                artifact=ArtifactRef(**item["artifact"]),
                execution_order=item["execution_order"],
                variables=item["variables"],
                timeout_seconds=item["timeout_seconds"],
                on_failure=item["on_failure"],
            )
            for item in payload["resources"]
        ]
        return DesiredState(
            host_id=host_id,
            revision=payload["revision"],
            checksum=payload["checksum"],
            generated_at=utcnow(),
            resources=resources,
        )
