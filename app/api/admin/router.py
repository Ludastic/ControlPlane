from fastapi import APIRouter

from app.schemas.admin import (
    AdminLoginRequest,
    AdminLoginResponse,
    EffectivePoliciesResponse,
    ExecutionRunListResponse,
    GroupCreateRequest,
    GroupListResponse,
    GroupResponse,
    GroupUpdateRequest,
    HostListResponse,
    HostResponse,
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
from app.services.control_plane_service import control_plane_service


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/auth/login", response_model=AdminLoginResponse)
def login(payload: AdminLoginRequest) -> AdminLoginResponse:
    return control_plane_service.admin_login(payload)


@router.get("/hosts", response_model=HostListResponse)
def list_hosts() -> HostListResponse:
    return control_plane_service.list_hosts()


@router.get("/hosts/{host_id}", response_model=HostResponse)
def get_host(host_id: str) -> HostResponse:
    return control_plane_service.get_host(host_id)


@router.get("/hosts/{host_id}/desired-state", response_model=DesiredState)
def get_host_desired_state(host_id: str) -> DesiredState:
    return control_plane_service.get_host_desired_state(host_id)


@router.get("/hosts/{host_id}/inventory", response_model=InventoryResponse)
def get_host_inventory(host_id: str) -> InventoryResponse:
    return control_plane_service.get_host_inventory(host_id)


@router.get("/hosts/{host_id}/effective-policies", response_model=EffectivePoliciesResponse)
def get_host_effective_policies(host_id: str) -> EffectivePoliciesResponse:
    return control_plane_service.get_host_effective_policies(host_id)


@router.get("/execution-runs", response_model=ExecutionRunListResponse)
def list_execution_runs() -> ExecutionRunListResponse:
    return control_plane_service.list_execution_runs()


@router.get("/groups", response_model=GroupListResponse)
def list_groups() -> GroupListResponse:
    return control_plane_service.list_groups()


@router.post("/groups", response_model=GroupResponse, status_code=201)
def create_group(payload: GroupCreateRequest) -> GroupResponse:
    return control_plane_service.create_group(payload)


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(group_id: str) -> GroupResponse:
    return control_plane_service.get_group(group_id)


@router.patch("/groups/{group_id}", response_model=GroupResponse)
def update_group(group_id: str, payload: GroupUpdateRequest) -> GroupResponse:
    return control_plane_service.update_group(group_id, payload)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: str) -> None:
    control_plane_service.delete_group(group_id)


@router.get("/policies", response_model=PolicyListResponse)
def list_policies() -> PolicyListResponse:
    return control_plane_service.list_policies()


@router.post("/policies", response_model=PolicyResponse, status_code=201)
def create_policy(payload: PolicyCreateRequest) -> PolicyResponse:
    return control_plane_service.create_policy(payload)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str) -> PolicyResponse:
    return control_plane_service.get_policy(policy_id)


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
def update_policy(policy_id: str, payload: PolicyUpdateRequest) -> PolicyResponse:
    return control_plane_service.update_policy(policy_id, payload)


@router.delete("/policies/{policy_id}", status_code=204)
def delete_policy(policy_id: str) -> None:
    control_plane_service.delete_policy(policy_id)


@router.get("/policies/{policy_id}/assignments", response_model=PolicyAssignmentListResponse)
def list_policy_assignments(policy_id: str) -> PolicyAssignmentListResponse:
    return control_plane_service.list_policy_assignments(policy_id)


@router.post("/policies/{policy_id}/assignments", response_model=PolicyAssignmentResponse, status_code=201)
def create_policy_assignment(
    policy_id: str,
    payload: PolicyAssignmentCreateRequest,
) -> PolicyAssignmentResponse:
    return control_plane_service.create_policy_assignment(policy_id, payload)


@router.delete("/policies/{policy_id}/assignments/{assignment_id}", status_code=204)
def delete_policy_assignment(policy_id: str, assignment_id: str) -> None:
    control_plane_service.delete_policy_assignment(policy_id, assignment_id)


@router.get("/playbooks", response_model=PlaybookListResponse)
def list_playbooks() -> PlaybookListResponse:
    return control_plane_service.list_playbooks()


@router.post("/playbooks", response_model=PlaybookResponse, status_code=201)
def create_playbook(payload: PlaybookCreateRequest) -> PlaybookResponse:
    return control_plane_service.create_playbook(payload)


@router.get("/playbooks/{playbook_id}", response_model=PlaybookResponse)
def get_playbook(playbook_id: str) -> PlaybookResponse:
    return control_plane_service.get_playbook(playbook_id)


@router.patch("/playbooks/{playbook_id}", response_model=PlaybookResponse)
def update_playbook(playbook_id: str, payload: PlaybookUpdateRequest) -> PlaybookResponse:
    return control_plane_service.update_playbook(playbook_id, payload)


@router.delete("/playbooks/{playbook_id}", status_code=204)
def delete_playbook(playbook_id: str) -> None:
    control_plane_service.delete_playbook(playbook_id)


@router.get("/playbooks/{playbook_id}/versions", response_model=PlaybookVersionListResponse)
def list_playbook_versions(playbook_id: str) -> PlaybookVersionListResponse:
    return control_plane_service.list_playbook_versions(playbook_id)


@router.post("/playbooks/{playbook_id}/versions", response_model=PlaybookVersionResponse, status_code=201)
def create_playbook_version(
    playbook_id: str,
    payload: PlaybookVersionCreateRequest,
) -> PlaybookVersionResponse:
    return control_plane_service.create_playbook_version(playbook_id, payload)


@router.get("/policies/{policy_id}/resources", response_model=PolicyResourceListResponse)
def list_policy_resources(policy_id: str) -> PolicyResourceListResponse:
    return control_plane_service.list_policy_resources(policy_id)


@router.post("/policies/{policy_id}/resources", response_model=PolicyResourceResponse, status_code=201)
def create_policy_resource(
    policy_id: str,
    payload: PolicyResourceCreateRequest,
) -> PolicyResourceResponse:
    return control_plane_service.create_policy_resource(policy_id, payload)


@router.patch("/policies/{policy_id}/resources/{resource_id}", response_model=PolicyResourceResponse)
def update_policy_resource(
    policy_id: str,
    resource_id: str,
    payload: PolicyResourceUpdateRequest,
) -> PolicyResourceResponse:
    return control_plane_service.update_policy_resource(policy_id, resource_id, payload)


@router.delete("/policies/{policy_id}/resources/{resource_id}", status_code=204)
def delete_policy_resource(policy_id: str, resource_id: str) -> None:
    control_plane_service.delete_policy_resource(policy_id, resource_id)
