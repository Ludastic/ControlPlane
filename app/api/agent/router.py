from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, Security, status
from fastapi.responses import Response as RawResponse

from app.api.dependencies import get_control_plane_service
from app.api.security import agent_bearer_scheme, build_authorization_header
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
from app.services.control_plane_service import ControlPlaneService


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/register", response_model=AgentRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_agent(
    payload: AgentRegistrationRequest,
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)],
) -> AgentRegistrationResponse:
    return service.register_agent(payload)


@router.post("/heartbeat", response_model=AgentHeartbeatResponse)
def heartbeat(
    payload: AgentHeartbeatRequest,
    credentials=Security(agent_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> AgentHeartbeatResponse:
    return service.heartbeat(token=build_authorization_header(credentials), payload=payload)


@router.get("/desired-state", response_model=DesiredState)
def get_desired_state(
    response: Response,
    credentials=Security(agent_bearer_scheme),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> DesiredState:
    desired_state = service.get_desired_state(token=build_authorization_header(credentials))
    etag = f"state-{desired_state.revision}"
    response.headers["ETag"] = etag
    if if_none_match == etag:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)
    return desired_state


@router.get("/artifacts/{artifact_id}", response_model=ArtifactMetadataResponse)
def get_artifact_metadata(
    artifact_id: str,
    credentials=Security(agent_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> ArtifactMetadataResponse:
    return service.get_artifact_metadata(token=build_authorization_header(credentials), artifact_id=artifact_id)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    credentials=Security(agent_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> RawResponse:
    artifact = service.download_artifact(token=build_authorization_header(credentials), artifact_id=artifact_id)
    return RawResponse(
        content=artifact["content"],
        media_type=artifact["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{artifact["filename"]}"'},
    )


@router.put("/inventory", response_model=AgentInventoryResponse)
def update_inventory(
    payload: dict,
    credentials=Security(agent_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> AgentInventoryResponse:
    return service.update_inventory(token=build_authorization_header(credentials), payload=payload)


@router.post("/execution-runs", response_model=ExecutionRunCreateResponse, status_code=status.HTTP_201_CREATED)
def create_execution_run(
    payload: ExecutionRunCreateRequest,
    credentials=Security(agent_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> ExecutionRunCreateResponse:
    return service.create_execution_run(token=build_authorization_header(credentials), payload=payload)


@router.post("/execution-runs/{run_id}/events", response_model=ExecutionEventsResponse, status_code=status.HTTP_202_ACCEPTED)
def report_execution_events(
    run_id: str,
    payload: ExecutionEventsRequest,
    credentials=Security(agent_bearer_scheme),
    service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
) -> ExecutionEventsResponse:
    return service.record_execution_events(
        token=build_authorization_header(credentials),
        run_id=run_id,
        payload=payload,
    )
