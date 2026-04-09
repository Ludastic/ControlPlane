from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import Response as RawResponse

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
)
from app.schemas.desired_state import DesiredState
from app.services.control_plane_service import control_plane_service


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/register", response_model=AgentRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentRegistrationRequest) -> AgentRegistrationResponse:
    return control_plane_service.register_agent(payload)


@router.post("/heartbeat", response_model=AgentHeartbeatResponse)
def heartbeat(
    payload: AgentHeartbeatRequest,
    authorization: str | None = Header(default=None),
) -> AgentHeartbeatResponse:
    return control_plane_service.heartbeat(token=authorization, payload=payload)


@router.get("/desired-state", response_model=DesiredState)
def get_desired_state(
    response: Response,
    authorization: str | None = Header(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> DesiredState:
    desired_state = control_plane_service.get_desired_state(token=authorization)
    etag = f"state-{desired_state.revision}"
    response.headers["ETag"] = etag
    if if_none_match == etag:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)
    return desired_state


@router.get("/artifacts/{artifact_id}", response_model=ArtifactMetadataResponse)
def get_artifact_metadata(
    artifact_id: str,
    authorization: str | None = Header(default=None),
) -> ArtifactMetadataResponse:
    return control_plane_service.get_artifact_metadata(token=authorization, artifact_id=artifact_id)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    authorization: str | None = Header(default=None),
) -> RawResponse:
    artifact = control_plane_service.download_artifact(token=authorization, artifact_id=artifact_id)
    return RawResponse(
        content=artifact["content"],
        media_type=artifact["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{artifact["filename"]}"'},
    )


@router.put("/inventory", response_model=AgentInventoryResponse)
def update_inventory(
    payload: dict,
    authorization: str | None = Header(default=None),
) -> AgentInventoryResponse:
    return control_plane_service.update_inventory(token=authorization, payload=payload)


@router.post("/execution-runs", response_model=ExecutionRunCreateResponse, status_code=status.HTTP_201_CREATED)
def create_execution_run(
    payload: ExecutionRunCreateRequest,
    authorization: str | None = Header(default=None),
) -> ExecutionRunCreateResponse:
    return control_plane_service.create_execution_run(token=authorization, payload=payload)


@router.post("/execution-runs/{run_id}/events", response_model=ExecutionEventsResponse, status_code=status.HTTP_202_ACCEPTED)
def report_execution_events(
    run_id: str,
    payload: ExecutionEventsRequest,
    authorization: str | None = Header(default=None),
) -> ExecutionEventsResponse:
    return control_plane_service.record_execution_events(
        token=authorization,
        run_id=run_id,
        payload=payload,
    )
