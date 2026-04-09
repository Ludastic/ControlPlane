from typing import Annotated

from fastapi import APIRouter, Depends, Response, Security, status

from app.api.admin.dependencies import require_admin_permission
from app.api.dependencies import get_control_plane_service
from app.api.security import admin_bearer_scheme, build_authorization_header
from app.core import rbac
from app.schemas.admin import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
    AdminRefreshRequest,
    AuditLogListResponse,
    AdminTokenResponse,
    AgentTokenResponse,
    EffectivePoliciesResponse,
    ExecutionRunListResponse,
    GroupCreateRequest,
    GroupListResponse,
    GroupResponse,
    GroupUpdateRequest,
    HostComplianceResponse,
    HostListResponse,
    HostResponse,
    InventoryHistoryResponse,
    InventoryResponse,
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
from app.schemas.desired_state import DesiredState
from app.services.control_plane_service import ControlPlaneService


read_access = Depends(require_admin_permission(rbac.READ))
write_access = Depends(require_admin_permission(rbac.WRITE))
admin_only = Depends(require_admin_permission(rbac.ADMIN))

auth_router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[read_access])


@auth_router.post("/login", response_model=AdminLoginResponse)
def login(
    payload: AdminLoginRequest,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> AdminLoginResponse:
    return service.admin_login(payload)


@auth_router.post("/refresh", response_model=AdminTokenResponse)
def refresh(
    payload: AdminRefreshRequest,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> AdminTokenResponse:
    return service.admin_refresh(payload)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials=Security(admin_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> Response:
    service.admin_logout(build_authorization_header(credentials))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get("/me", response_model=AdminMeResponse, dependencies=[read_access])
def get_me(
    credentials=Security(admin_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> AdminMeResponse:
    return service.get_admin_me(build_authorization_header(credentials))


@router.get("/hosts", response_model=HostListResponse)
def list_hosts(service: Annotated[ControlPlaneService, Depends(get_control_plane_service)]) -> HostListResponse:
    return service.list_hosts()


@router.get("/audit-log", response_model=AuditLogListResponse)
def list_audit_log(
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
    user_id: str | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    limit: int | None = None,
) -> AuditLogListResponse:
    return service.list_audit_log(user_id=user_id, entity_type=entity_type, action=action, limit=limit)


@router.get("/hosts/{host_id}", response_model=HostResponse)
def get_host(
    host_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> HostResponse:
    return service.get_host(host_id)


@router.post("/hosts/{host_id}/agent-token/rotate", response_model=AgentTokenResponse, dependencies=[write_access])
def rotate_host_agent_token(
    host_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> AgentTokenResponse:
    return service.rotate_host_agent_token(host_id, actor=admin)


@router.post("/hosts/{host_id}/agent-token/revoke", status_code=204, dependencies=[admin_only])
def revoke_host_agent_token(
    host_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.ADMIN))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> None:
    service.revoke_host_agent_token(host_id, actor=admin)


@router.get("/hosts/{host_id}/desired-state", response_model=DesiredState)
def get_host_desired_state(
    host_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> DesiredState:
    return service.get_host_desired_state(host_id)


@router.get("/hosts/{host_id}/inventory", response_model=InventoryResponse)
def get_host_inventory(
    host_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> InventoryResponse:
    return service.get_host_inventory(host_id)


@router.get("/hosts/{host_id}/inventory/history", response_model=InventoryHistoryResponse)
def get_host_inventory_history(
    host_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
    limit: int | None = None,
) -> InventoryHistoryResponse:
    return service.get_host_inventory_history(host_id, limit=limit)


@router.get("/hosts/{host_id}/effective-policies", response_model=EffectivePoliciesResponse)
def get_host_effective_policies(
    host_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> EffectivePoliciesResponse:
    return service.get_host_effective_policies(host_id)


@router.get("/hosts/{host_id}/compliance", response_model=HostComplianceResponse)
def get_host_compliance(
    host_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> HostComplianceResponse:
    return service.get_host_compliance(host_id)


@router.get("/execution-runs", response_model=ExecutionRunListResponse)
def list_execution_runs(
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
    host_id: str | None = None,
    status: str | None = None,
) -> ExecutionRunListResponse:
    return service.list_execution_runs(host_id=host_id, aggregate_status=status)


@router.get("/groups", response_model=GroupListResponse)
def list_groups(service: Annotated[ControlPlaneService, Depends(get_control_plane_service)]) -> GroupListResponse:
    return service.list_groups()


@router.post("/groups", response_model=GroupResponse, status_code=201, dependencies=[write_access])
def create_group(
    payload: GroupCreateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> GroupResponse:
    return service.create_group(payload, actor=admin)


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> GroupResponse:
    return service.get_group(group_id)


@router.patch("/groups/{group_id}", response_model=GroupResponse, dependencies=[write_access])
def update_group(
    group_id: str,
    payload: GroupUpdateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> GroupResponse:
    return service.update_group(group_id, payload, actor=admin)


@router.delete("/groups/{group_id}", status_code=204, dependencies=[admin_only])
def delete_group(
    group_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.ADMIN))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> None:
    service.delete_group(group_id, actor=admin)


@router.get("/policies", response_model=PolicyListResponse)
def list_policies(service: Annotated[ControlPlaneService, Depends(get_control_plane_service)]) -> PolicyListResponse:
    return service.list_policies()


@router.post("/policies", response_model=PolicyResponse, status_code=201, dependencies=[write_access])
def create_policy(
    payload: PolicyCreateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyResponse:
    return service.create_policy(payload, actor=admin)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(
    policy_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyResponse:
    return service.get_policy(policy_id)


@router.patch("/policies/{policy_id}", response_model=PolicyResponse, dependencies=[write_access])
def update_policy(
    policy_id: str,
    payload: PolicyUpdateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyResponse:
    return service.update_policy(policy_id, payload, actor=admin)


@router.delete("/policies/{policy_id}", status_code=204, dependencies=[admin_only])
def delete_policy(
    policy_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.ADMIN))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> None:
    service.delete_policy(policy_id, actor=admin)


@router.get("/policies/{policy_id}/assignments", response_model=PolicyAssignmentListResponse)
def list_policy_assignments(
    policy_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyAssignmentListResponse:
    return service.list_policy_assignments(policy_id)


@router.post("/policies/{policy_id}/assignments", response_model=PolicyAssignmentResponse, status_code=201, dependencies=[write_access])
def create_policy_assignment(
    policy_id: str,
    payload: PolicyAssignmentCreateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyAssignmentResponse:
    return service.create_policy_assignment(policy_id, payload, actor=admin)


@router.delete("/policies/{policy_id}/assignments/{assignment_id}", status_code=204, dependencies=[admin_only])
def delete_policy_assignment(
    policy_id: str,
    assignment_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.ADMIN))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> None:
    service.delete_policy_assignment(policy_id, assignment_id, actor=admin)


@router.get("/playbooks", response_model=PlaybookListResponse)
def list_playbooks(service: Annotated[ControlPlaneService, Depends(get_control_plane_service)]) -> PlaybookListResponse:
    return service.list_playbooks()


@router.post("/playbooks", response_model=PlaybookResponse, status_code=201, dependencies=[write_access])
def create_playbook(
    payload: PlaybookCreateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PlaybookResponse:
    return service.create_playbook(payload, actor=admin)


@router.get("/playbooks/{playbook_id}", response_model=PlaybookResponse)
def get_playbook(
    playbook_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PlaybookResponse:
    return service.get_playbook(playbook_id)


@router.patch("/playbooks/{playbook_id}", response_model=PlaybookResponse, dependencies=[write_access])
def update_playbook(
    playbook_id: str,
    payload: PlaybookUpdateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PlaybookResponse:
    return service.update_playbook(playbook_id, payload, actor=admin)


@router.delete("/playbooks/{playbook_id}", status_code=204, dependencies=[admin_only])
def delete_playbook(
    playbook_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.ADMIN))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> None:
    service.delete_playbook(playbook_id, actor=admin)


@router.get("/playbooks/{playbook_id}/versions", response_model=PlaybookVersionListResponse)
def list_playbook_versions(
    playbook_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PlaybookVersionListResponse:
    return service.list_playbook_versions(playbook_id)


@router.post("/playbooks/{playbook_id}/versions", response_model=PlaybookVersionResponse, status_code=201, dependencies=[write_access])
def create_playbook_version(
    playbook_id: str,
    payload: PlaybookVersionCreateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PlaybookVersionResponse:
    return service.create_playbook_version(playbook_id, payload, actor=admin)


@router.get("/policies/{policy_id}/resources", response_model=PolicyResourceListResponse)
def list_policy_resources(
    policy_id: str,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyResourceListResponse:
    return service.list_policy_resources(policy_id)


@router.post("/policies/{policy_id}/resources", response_model=PolicyResourceResponse, status_code=201, dependencies=[write_access])
def create_policy_resource(
    policy_id: str,
    payload: PolicyResourceCreateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyResourceResponse:
    return service.create_policy_resource(policy_id, payload, actor=admin)


@router.patch("/policies/{policy_id}/resources/{resource_id}", response_model=PolicyResourceResponse, dependencies=[write_access])
def update_policy_resource(
    policy_id: str,
    resource_id: str,
    payload: PolicyResourceUpdateRequest,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.WRITE))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> PolicyResourceResponse:
    return service.update_policy_resource(policy_id, resource_id, payload, actor=admin)


@router.delete("/policies/{policy_id}/resources/{resource_id}", status_code=204, dependencies=[admin_only])
def delete_policy_resource(
    policy_id: str,
    resource_id: str,
    admin: Annotated[AdminMeResponse, Depends(require_admin_permission(rbac.ADMIN))],
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> None:
    service.delete_policy_resource(policy_id, resource_id, actor=admin)
