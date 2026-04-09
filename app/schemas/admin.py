from datetime import datetime

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(default=3600, ge=1)


class AdminLoginResponse(AdminTokenResponse):
    pass


class AdminRefreshRequest(BaseModel):
    refresh_token: str


class AdminMeResponse(BaseModel):
    user_id: str
    username: str
    role: str
    is_active: bool


class AgentTokenResponse(BaseModel):
    host_id: str
    agent_token: str
    rotated_at: datetime


class AuditLogEntryResponse(BaseModel):
    audit_id: str
    actor_user_id: str | None = None
    actor_username: str
    action: str
    entity_type: str
    entity_id: str | None = None
    details: dict | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntryResponse]
    total: int = Field(ge=0)


class HostResponse(BaseModel):
    host_id: str
    agent_id: str
    hostname: str
    fqdn: str
    status: str
    registered_at: datetime
    last_seen_at: datetime | None = None


class HostListResponse(BaseModel):
    items: list[HostResponse]
    total: int = Field(ge=0)


class InventoryResponse(BaseModel):
    host_id: str
    snapshot_version: int = Field(ge=1)
    data: dict


class InventoryHistoryItem(BaseModel):
    snapshot_version: int = Field(ge=1)
    collected_at: datetime
    data: dict


class InventoryHistoryResponse(BaseModel):
    host_id: str
    items: list[InventoryHistoryItem]
    total: int = Field(ge=0)


class ExecutionRunResponse(BaseModel):
    run_id: str
    host_id: str
    state_revision: int = Field(ge=1)
    started_at: datetime
    reported_at: datetime | None = None
    events_count: int = Field(ge=0)
    aggregate_status: str


class ExecutionRunListResponse(BaseModel):
    items: list[ExecutionRunResponse]
    total: int = Field(ge=0)


class EffectivePoliciesResponse(BaseModel):
    host_id: str
    items: list[dict]


class GroupCreateRequest(BaseModel):
    name: str
    description: str | None = None


class GroupUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupResponse(BaseModel):
    group_id: str
    name: str
    description: str | None = None


class GroupListResponse(BaseModel):
    items: list[GroupResponse]
    total: int = Field(ge=0)


class PolicyCreateRequest(BaseModel):
    name: str
    description: str | None = None
    priority: int = Field(default=100, ge=0)
    is_active: bool = True


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PolicyResponse(BaseModel):
    policy_id: str
    name: str
    description: str | None = None
    priority: int = Field(ge=0)
    is_active: bool


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]
    total: int = Field(ge=0)


class PolicyAssignmentCreateRequest(BaseModel):
    target_type: str
    target_id: str | None = None


class PolicyAssignmentResponse(BaseModel):
    assignment_id: str
    policy_id: str
    target_type: str
    target_id: str | None = None


class PolicyAssignmentListResponse(BaseModel):
    items: list[PolicyAssignmentResponse]
    total: int = Field(ge=0)


class PlaybookCreateRequest(BaseModel):
    name: str
    description: str | None = None


class PlaybookUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class PlaybookResponse(BaseModel):
    playbook_id: str
    name: str
    description: str | None = None


class PlaybookListResponse(BaseModel):
    items: list[PlaybookResponse]
    total: int = Field(ge=0)


class PlaybookVersionCreateRequest(BaseModel):
    version: str
    checksum: str


class PlaybookVersionResponse(BaseModel):
    artifact_id: str
    playbook_id: str
    version: str
    checksum: str
    immutable: bool = True


class PlaybookVersionListResponse(BaseModel):
    items: list[PlaybookVersionResponse]
    total: int = Field(ge=0)


class PolicyResourceCreateRequest(BaseModel):
    type: str = "ansible_playbook"
    playbook_id: str
    playbook_version: str
    execution_order: int = Field(default=10, ge=0)
    variables: dict = Field(default_factory=dict)
    on_failure: str = "stop"


class PolicyResourceUpdateRequest(BaseModel):
    playbook_version: str | None = None
    execution_order: int | None = Field(default=None, ge=0)
    variables: dict | None = None
    on_failure: str | None = None


class PolicyResourceResponse(BaseModel):
    resource_id: str
    policy_id: str
    type: str
    playbook_id: str
    playbook_version: str
    execution_order: int = Field(ge=0)
    variables: dict
    on_failure: str


class PolicyResourceListResponse(BaseModel):
    items: list[PolicyResourceResponse]
    total: int = Field(ge=0)
