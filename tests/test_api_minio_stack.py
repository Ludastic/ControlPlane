from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest

from app.services.checksums import sha256_digest


STACK_API_URL = os.getenv("CONTROL_PLANE_STACK_API_URL")

pytestmark = pytest.mark.skipif(
    not STACK_API_URL,
    reason="CONTROL_PLANE_STACK_API_URL is not configured",
)


def _admin_login(client: httpx.Client) -> str:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def test_compose_stack_artifact_flow() -> None:
    assert STACK_API_URL is not None

    with httpx.Client(base_url=STACK_API_URL, timeout=30.0) as client:
        ready_response = client.get("/ready")
        assert ready_response.status_code == 200
        assert ready_response.json()["checks"]["artifact_storage"]["status"] == "ok"

        access_token = _admin_login(client)
        admin_headers = {"Authorization": f"Bearer {access_token}"}

        playbook_name = f"stack-playbook-{uuid4().hex[:8]}"
        create_playbook_response = client.post(
            "/api/v1/admin/playbooks",
            headers=admin_headers,
            json={"name": playbook_name, "description": "Compose stack integration test"},
        )
        create_playbook_response.raise_for_status()
        playbook_id = create_playbook_response.json()["playbook_id"]

        version = "1.0.0"
        checksum = sha256_digest(f"artifact:{playbook_id}:{version}".encode("utf-8"))
        create_version_response = client.post(
            f"/api/v1/admin/playbooks/{playbook_id}/versions",
            headers=admin_headers,
            json={"version": version, "checksum": checksum},
        )
        create_version_response.raise_for_status()
        artifact_id = create_version_response.json()["artifact_id"]

        register_response = client.post(
            "/api/v1/agent/register",
            json={
                "agent_id": f"stack-agent-{uuid4().hex[:8]}",
                "registration_token": "bootstrap-secret",
                "hostname": "stack-agent",
                "fqdn": "stack-agent.local",
                "os_name": "Ubuntu",
                "os_version": "24.04",
                "kernel_version": "6.8.0",
                "architecture": "x86_64",
                "ip_addresses": ["10.10.10.10"],
                "agent_version": "0.1.0",
            },
        )
        register_response.raise_for_status()
        agent_headers = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}

        metadata_response = client.get(
            f"/api/v1/agent/artifacts/{artifact_id}",
            headers=agent_headers,
        )
        metadata_response.raise_for_status()
        assert metadata_response.json()["artifact_id"] == artifact_id
        assert metadata_response.json()["checksum"] == checksum

        download_response = client.get(
            f"/api/v1/agent/artifacts/{artifact_id}/download",
            headers=agent_headers,
        )
        download_response.raise_for_status()
        assert download_response.content == f"artifact:{playbook_id}:{version}".encode("utf-8")
