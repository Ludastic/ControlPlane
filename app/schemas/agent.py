from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentRegistrationRequest(BaseModel):
    agent_id: str
    registration_token: str
    hostname: str
    fqdn: str
    os_name: str
    os_version: str
    kernel_version: str
    architecture: str
    ip_addresses: list[str]
    agent_version: str


class AgentRegistrationResponse(BaseModel):
    host_id: str
    agent_token: str
    poll_interval_seconds: int = Field(default=60, ge=1)
    registered_at: datetime


class AgentHeartbeatRequest(BaseModel):
    agent_version: str
    status: Literal["online", "degraded", "offline"]


class AgentHeartbeatResponse(BaseModel):
    server_time: datetime
    poll_interval_seconds: int = Field(default=60, ge=1)


class AgentInventoryResponse(BaseModel):
    accepted: bool
    snapshot_version: int = Field(ge=1)


class ExecutionRunCreateRequest(BaseModel):
    state_revision: int = Field(ge=1)
    started_at: datetime


class ExecutionRunCreateResponse(BaseModel):
    run_id: str
    accepted: bool


class ExecutionEventItem(BaseModel):
    event_id: str | None = None
    resource_id: str
    artifact_id: str
    status: Literal["pending", "running", "success", "failed", "skipped", "cancelled", "outdated"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None


class ExecutionEventsRequest(BaseModel):
    reported_at: datetime
    items: list[ExecutionEventItem]


class ExecutionEventsResponse(BaseModel):
    accepted: bool
    processed_items: int = Field(ge=0)


class InventorySnapshot(BaseModel):
    collected_at: datetime
    os_name: str
    os_version: str
    kernel_version: str
    architecture: str
    hostname: str
    fqdn: str
    ip_addresses: list[str]
    cpu_info: dict[str, Any] | None = None
    memory_mb: int | None = Field(default=None, ge=1)
    disk: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class ArtifactMetadataResponse(BaseModel):
    artifact_id: str
    name: str
    version: str
    checksum: str
    content_type: str
    size_bytes: int = Field(ge=0)
    download_url: str
