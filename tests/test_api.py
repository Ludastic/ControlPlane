import pytest
from fastapi.testclient import TestClient
from app.core.settings import settings
from app.services.checksums import sha256_digest
from app.services.artifact_storage import artifact_storage


def _admin_headers(client: TestClient, username: str = "admin", password: str = "admin") -> dict[str, str]:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_healthcheck(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_swagger_and_openapi_endpoints_are_available(client: TestClient) -> None:
    docs_response = client.get("/docs")
    redoc_response = client.get("/redoc")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert redoc_response.status_code == 200
    assert openapi_response.status_code == 200
    assert openapi_response.json()["info"]["title"] == "Control Plane API"
    assert any(tag["name"] == "agent" for tag in openapi_response.json()["tags"])


def test_readinesscheck_on_memory_backend(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_backend", "memory")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["database"]["status"] == "skipped"
    assert response.json()["checks"]["artifact_storage"]["status"] == "ok"


def test_agent_desired_state_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/agent/desired-state")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_AGENT_TOKEN"


def test_agent_register_rejects_invalid_registration_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-invalid-01",
            "registration_token": "wrong-token",
            "hostname": "ws-invalid-01",
            "fqdn": "ws-invalid-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.31"],
            "agent_version": "0.1.0",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REGISTRATION_TOKEN"


def test_agent_desired_state_returns_payload_for_demo_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer demo-agent-token"},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["host_id"] == "host_demo_01"
    assert payload["revision"] >= 1
    assert payload["checksum"].startswith("sha256:")
    assert len(payload["resources"]) == 2


def test_admin_unknown_host_returns_unified_error(client: TestClient) -> None:
    response = client.get("/api/v1/admin/hosts/unknown", headers=_admin_headers(client))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HOST_NOT_FOUND"


def test_admin_login_and_me_flow(client: TestClient) -> None:
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    access_token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"
    assert me_response.json()["role"] == "admin"


def test_admin_refresh_and_logout_flow(client: TestClient) -> None:
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/admin/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    logout_response = client.post(
        "/api/v1/admin/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    revoked_me_response = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert refresh_response.status_code == 200
    assert logout_response.status_code == 204
    assert revoked_me_response.status_code == 401
    assert revoked_me_response.json()["error"]["code"] == "INVALID_ADMIN_TOKEN"

    audit_response = client.get(
        "/api/v1/admin/audit-log?action=admin.logout",
        headers=_admin_headers(client),
    )

    assert audit_response.status_code == 200
    assert audit_response.json()["total"] >= 1
    assert audit_response.json()["items"][0]["action"] == "admin.logout"


def test_admin_auditor_cannot_mutate_groups(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/groups",
        headers=_admin_headers(client, username="auditor", password="auditor"),
        json={"name": "Forbidden Group", "description": "Should not be created"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_FORBIDDEN"


def test_admin_operator_can_write_but_cannot_delete_groups(client: TestClient) -> None:
    operator_headers = _admin_headers(client, username="operator", password="operator")
    create_response = client.post(
        "/api/v1/admin/groups",
        headers=operator_headers,
        json={"name": "Operator Group", "description": "Created by operator"},
    )
    group_id = create_response.json()["group_id"]
    delete_response = client.delete(
        f"/api/v1/admin/groups/{group_id}",
        headers=operator_headers,
    )

    assert create_response.status_code == 201
    assert delete_response.status_code == 403
    assert delete_response.json()["error"]["code"] == "ADMIN_FORBIDDEN"


def test_policy_resources_list_returns_seeded_binding(client: TestClient) -> None:
    response = client.get("/api/v1/admin/policies/pol_global_base/resources", headers=_admin_headers(client))

    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["items"][0]["playbook_id"] == "pb_base"


def test_effective_policies_are_computed_from_assignments(client: TestClient) -> None:
    response = client.get("/api/v1/admin/hosts/host_demo_01/effective-policies", headers=_admin_headers(client))

    payload = response.json()

    assert response.status_code == 200
    assert payload["host_id"] == "host_demo_01"
    assert len(payload["items"]) == 2
    assert {item["scope"] for item in payload["items"]} == {"global", "group"}


def test_groups_crud_flow(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    create_response = client.post("/api/v1/admin/groups", headers=admin_headers, json={"name": "Support", "description": "Support workstations"})
    created = create_response.json()
    group_id = created["group_id"]

    update_response = client.patch(f"/api/v1/admin/groups/{group_id}", headers=admin_headers, json={"description": "Updated description"})
    get_response = client.get(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    delete_response = client.delete(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    missing_response = client.get(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    audit_response = client.get("/api/v1/admin/audit-log?entity_type=group", headers=admin_headers)

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["description"] == "Updated description"
    assert delete_response.status_code == 204
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "GROUP_NOT_FOUND"
    assert audit_response.status_code == 200
    assert [item["action"] for item in audit_response.json()["items"][:3]] == [
        "group.delete",
        "group.update",
        "group.create",
    ]


def test_policies_assignments_and_resources_flow(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    policy_response = client.post("/api/v1/admin/policies", headers=admin_headers, json={"name": "VPN policy", "priority": 300, "is_active": True})
    policy_id = policy_response.json()["policy_id"]

    assignment_response = client.post(
        f"/api/v1/admin/policies/{policy_id}/assignments",
        headers=admin_headers,
        json={"target_type": "group", "target_id": "grp_eng"},
    )
    resource_response = client.post(
        f"/api/v1/admin/policies/{policy_id}/resources",
        headers=admin_headers,
        json={
            "playbook_id": "pb_vpn",
            "playbook_version": "2.0.1",
            "execution_order": 50,
            "variables": {"vpn_server": "vpn.company.local"},
            "on_failure": "continue",
        },
    )
    resource_id = resource_response.json()["resource_id"]

    patch_response = client.patch(
        f"/api/v1/admin/policies/{policy_id}/resources/{resource_id}",
        headers=admin_headers,
        json={"execution_order": 60},
    )
    list_response = client.get(f"/api/v1/admin/policies/{policy_id}/resources", headers=admin_headers)

    assert policy_response.status_code == 201
    assert assignment_response.status_code == 201
    assert resource_response.status_code == 201
    assert patch_response.status_code == 200
    assert patch_response.json()["execution_order"] == 60
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_playbooks_and_versions_flow(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    create_response = client.post("/api/v1/admin/playbooks", headers=admin_headers, json={"name": "hardening", "description": "Host hardening"})
    playbook_id = create_response.json()["playbook_id"]
    expected_checksum = sha256_digest(f"artifact:{playbook_id}:1.0.0".encode("utf-8"))

    version_response = client.post(
        f"/api/v1/admin/playbooks/{playbook_id}/versions",
        headers=admin_headers,
        json={"version": "1.0.0", "checksum": expected_checksum},
    )
    duplicate_response = client.post(
        f"/api/v1/admin/playbooks/{playbook_id}/versions",
        headers=admin_headers,
        json={"version": "1.0.0", "checksum": expected_checksum},
    )
    list_response = client.get(f"/api/v1/admin/playbooks/{playbook_id}/versions", headers=admin_headers)

    assert create_response.status_code == 201
    assert version_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "PLAYBOOK_VERSION_ALREADY_EXISTS"
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_playbook_version_rejects_checksum_mismatch(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    create_response = client.post(
        "/api/v1/admin/playbooks",
        headers=admin_headers,
        json={"name": "checksum-test", "description": "Checksum validation"},
    )
    playbook_id = create_response.json()["playbook_id"]

    response = client.post(
        f"/api/v1/admin/playbooks/{playbook_id}/versions",
        headers=admin_headers,
        json={"version": "1.0.0", "checksum": "sha256:deadbeef"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ARTIFACT_CHECKSUM_MISMATCH"


def test_agent_register_inventory_execution_flow(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-flow-01",
            "registration_token": "bootstrap-secret",
            "hostname": "ws-flow-01",
            "fqdn": "ws-flow-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.30"],
            "agent_version": "0.1.0",
        },
    )
    token = register_response.json()["agent_token"]
    auth = {"Authorization": f"Bearer {token}"}

    state_response = client.get("/api/v1/agent/desired-state", headers=auth)
    inventory_response = client.put(
        "/api/v1/agent/inventory",
        headers=auth,
        json={
            "collected_at": "2026-04-09T11:22:00Z",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "hostname": "ws-flow-01",
            "fqdn": "ws-flow-01.company.local",
            "ip_addresses": ["10.10.1.30"],
            "memory_mb": 8192,
            "disk": [],
            "extra": {},
        },
    )
    run_response = client.post(
        "/api/v1/agent/execution-runs",
        headers=auth,
        json={"state_revision": 1, "started_at": "2026-04-09T11:23:00Z"},
    )
    run_id = run_response.json()["run_id"]
    events_response = client.post(
        f"/api/v1/agent/execution-runs/{run_id}/events",
        headers=auth,
        json={
            "reported_at": "2026-04-09T11:24:00Z",
            "items": [
                {
                    "resource_id": "res_base",
                    "artifact_id": "art_base_01",
                    "status": "success",
                    "started_at": "2026-04-09T11:23:10Z",
                    "finished_at": "2026-04-09T11:23:40Z",
                    "message": "Applied",
                }
            ],
        },
    )
    runs_response = client.get("/api/v1/admin/execution-runs", headers=_admin_headers(client))

    assert register_response.status_code == 201
    assert state_response.status_code == 200
    assert inventory_response.status_code == 200
    assert run_response.status_code == 201
    assert events_response.status_code == 202
    assert runs_response.status_code == 200
    assert runs_response.json()["total"] == 1
    assert runs_response.json()["items"][0]["aggregate_status"] == "success"


def test_inventory_history_respects_retention_limit(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-inventory-01",
            "registration_token": "bootstrap-secret",
            "hostname": "ws-inventory-01",
            "fqdn": "ws-inventory-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.34"],
            "agent_version": "0.1.0",
        },
    )
    auth = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}
    for version in range(1, 8):
        client.put(
            "/api/v1/agent/inventory",
            headers=auth,
            json={
                "collected_at": f"2026-04-09T11:2{version}:00Z",
                "os_name": "Ubuntu",
                "os_version": "24.04",
                "kernel_version": "6.8.0",
                "architecture": "x86_64",
                "hostname": "ws-inventory-01",
                "fqdn": "ws-inventory-01.company.local",
                "ip_addresses": ["10.10.1.34"],
                "memory_mb": 4096 + version,
                "disk": [],
                "extra": {"version": version},
            },
        )

    latest_response = client.get(
        f"/api/v1/admin/hosts/{register_response.json()['host_id']}/inventory",
        headers=_admin_headers(client),
    )
    history_response = client.get(
        f"/api/v1/admin/hosts/{register_response.json()['host_id']}/inventory/history",
        headers=_admin_headers(client),
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["snapshot_version"] == 7
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 5
    assert history_response.json()["items"][0]["snapshot_version"] == 7
    assert history_response.json()["items"][-1]["snapshot_version"] == 3


def test_execution_runs_filter_by_failed_status(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-failed-flow-01",
            "registration_token": "bootstrap-secret",
            "hostname": "ws-failed-01",
            "fqdn": "ws-failed-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.32"],
            "agent_version": "0.1.0",
        },
    )
    auth = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}
    run_response = client.post(
        "/api/v1/agent/execution-runs",
        headers=auth,
        json={"state_revision": 1, "started_at": "2026-04-09T11:23:00Z"},
    )
    client.post(
        f"/api/v1/agent/execution-runs/{run_response.json()['run_id']}/events",
        headers=auth,
        json={
            "reported_at": "2026-04-09T11:24:00Z",
            "items": [
                {
                    "resource_id": "res_base",
                    "artifact_id": "art_base_01",
                    "status": "failed",
                    "started_at": "2026-04-09T11:23:10Z",
                    "finished_at": "2026-04-09T11:23:40Z",
                    "message": "Failed",
                }
            ],
        },
    )

    response = client.get(
        "/api/v1/admin/execution-runs?status=failed",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["aggregate_status"] == "failed"


def test_execution_events_are_idempotent_by_event_id(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-idempotent-01",
            "registration_token": "bootstrap-secret",
            "hostname": "ws-idempotent-01",
            "fqdn": "ws-idempotent-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.33"],
            "agent_version": "0.1.0",
        },
    )
    auth = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}
    run_response = client.post(
        "/api/v1/agent/execution-runs",
        headers=auth,
        json={"state_revision": 1, "started_at": "2026-04-09T11:23:00Z"},
    )
    payload = {
        "reported_at": "2026-04-09T11:24:00Z",
        "items": [
            {
                "event_id": "evt-001",
                "resource_id": "res_base",
                "artifact_id": "art_base_01",
                "status": "success",
                "started_at": "2026-04-09T11:23:10Z",
                "finished_at": "2026-04-09T11:23:40Z",
                "message": "Applied",
            }
        ],
    }
    client.post(f"/api/v1/agent/execution-runs/{run_response.json()['run_id']}/events", headers=auth, json=payload)
    client.post(f"/api/v1/agent/execution-runs/{run_response.json()['run_id']}/events", headers=auth, json=payload)

    response = client.get("/api/v1/admin/execution-runs", headers=_admin_headers(client))

    assert response.status_code == 200
    assert response.json()["items"][0]["events_count"] == 1


def test_agent_token_rotate_and_revoke_flow(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    rotate_response = client.post(
        "/api/v1/admin/hosts/host_demo_01/agent-token/rotate",
        headers=admin_headers,
    )
    new_token = rotate_response.json()["agent_token"]

    old_token_response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer demo-agent-token"},
    )
    new_token_response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    revoke_response = client.post(
        "/api/v1/admin/hosts/host_demo_01/agent-token/revoke",
        headers=admin_headers,
    )
    revoked_token_response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    assert rotate_response.status_code == 200
    assert old_token_response.status_code == 401
    assert new_token_response.status_code == 200
    assert revoke_response.status_code == 204
    assert revoked_token_response.status_code == 401


def test_agent_artifact_not_found_returns_unified_error(client: TestClient) -> None:
    response = client.get(
        "/api/v1/agent/artifacts/unknown",
        headers={"Authorization": "Bearer demo-agent-token"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_agent_artifact_checksum_mismatch_returns_unified_error(client: TestClient) -> None:
    artifact_storage.write_bytes("seed/base-config-1.0.0.tar.gz", b"tampered")

    response = client.get(
        "/api/v1/agent/artifacts/art_base_01",
        headers={"Authorization": "Bearer demo-agent-token"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ARTIFACT_CHECKSUM_MISMATCH"


def test_agent_desired_state_returns_304_for_matching_etag(client: TestClient) -> None:
    first_response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer demo-agent-token"},
    )

    etag = first_response.headers["etag"]

    second_response = client.get(
        "/api/v1/agent/desired-state",
        headers={
            "Authorization": "Bearer demo-agent-token",
            "If-None-Match": etag,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 304
    assert second_response.text == ""


def test_desired_state_returns_configuration_conflict_for_same_scope_and_priority(client: TestClient) -> None:
    policy_response = client.post(
        "/api/v1/admin/policies",
        headers=_admin_headers(client),
        json={"name": "Conflicting Group Policy", "priority": 200, "is_active": True},
    )
    policy_id = policy_response.json()["policy_id"]

    client.post(
        f"/api/v1/admin/policies/{policy_id}/assignments",
        headers=_admin_headers(client),
        json={"target_type": "group", "target_id": "grp_eng"},
    )
    client.post(
        f"/api/v1/admin/policies/{policy_id}/resources",
        headers=_admin_headers(client),
        json={
            "playbook_id": "pb_vpn",
            "playbook_version": "2.0.1",
            "execution_order": 20,
            "variables": {"vpn_server": "other.company.local"},
            "on_failure": "continue",
        },
    )

    response = client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer demo-agent-token"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFIGURATION_CONFLICT"
