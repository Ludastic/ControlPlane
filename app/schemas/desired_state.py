from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactRef(BaseModel):
    artifact_id: str
    playbook_id: str
    version: str
    checksum: str
    download_url: str


class DesiredResource(BaseModel):
    resource_id: str
    type: Literal["ansible_playbook"]
    name: str
    artifact: ArtifactRef
    execution_order: int = Field(ge=0)
    variables: dict[str, Any]
    timeout_seconds: int | None = Field(default=None, ge=1)
    on_failure: Literal["stop", "continue"]


class DesiredState(BaseModel):
    host_id: str
    revision: int = Field(ge=1)
    checksum: str
    generated_at: datetime
    resources: list[DesiredResource]
