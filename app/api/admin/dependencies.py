from typing import Annotated

from fastapi import Depends, Security

from app.api.dependencies import get_control_plane_service
from app.api.security import admin_bearer_scheme, build_authorization_header
from app.schemas.admin import AdminMeResponse
from app.services.control_plane_service import ControlPlaneService


def require_admin_permission(permission: str):
    def _dependency(
        credentials=Security(admin_bearer_scheme),
        service: Annotated[ControlPlaneService, Depends(get_control_plane_service)] = None,
    ) -> AdminMeResponse:
        return service.require_admin_permission(build_authorization_header(credentials), permission)

    return _dependency
