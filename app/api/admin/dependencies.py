from typing import Annotated

from fastapi import Depends, Header

from app.api.dependencies import get_control_plane_service
from app.schemas.admin import AdminMeResponse
from app.services.control_plane_service import ControlPlaneService


def require_admin_permission(permission: str):
    def _dependency(
        authorization: str | None = Header(default=None),
        service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
    ) -> AdminMeResponse:
        return service.require_admin_permission(authorization, permission)

    return _dependency
