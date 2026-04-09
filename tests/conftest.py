import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_control_plane_service
from app.main import app
from app.services.control_plane_service import ControlPlaneService


@pytest.fixture
def client() -> TestClient:
    service = ControlPlaneService()
    app.dependency_overrides[get_control_plane_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
