from fastapi.testclient import TestClient

from app.main import app


def create_test_client() -> TestClient:
    return TestClient(app)


def test_healthcheck() -> None:
    client: TestClient = create_test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_desired_state_requires_token() -> None:
    client: TestClient = create_test_client()

    response = client.get("/api/v1/agent/desired-state")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_AGENT_TOKEN"


def test_agent_desired_state_returns_payload_for_demo_token() -> None:
    client: TestClient = create_test_client()

    response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer demo-agent-token"},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["host_id"] == "host_demo_01"
    assert payload["revision"] == 1
    assert len(payload["resources"]) == 2


def test_admin_unknown_host_returns_unified_error() -> None:
    client: TestClient = create_test_client()

    response = client.get("/api/v1/admin/hosts/unknown")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HOST_NOT_FOUND"


def test_policy_resources_list_returns_seeded_binding() -> None:
    client: TestClient = create_test_client()

    response = client.get("/api/v1/admin/policies/pol_global_base/resources")

    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["items"][0]["playbook_id"] == "pb_base"
