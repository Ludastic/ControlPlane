from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.dependencies import get_control_plane_service
from app.core import readiness as readiness_module
from app.core.settings import settings
from app.db import init_db as init_db_module
from app.main import app
from app.models.artifact import Artifact
from app.models.group import Group, HostGroupMembership
from app.models.host import Host
from app.models.inventory import InventorySnapshot
from app.models.playbook import Playbook
from app.models.policy import Policy, PolicyAssignment, PolicyResource
from app.models.user import User
from app.core.security import hash_agent_token, hash_password
from app.services.checksums import sha256_digest
from app.services.artifact_storage import artifact_storage
from app.services.control_plane_service import ControlPlaneService
from app.repositories.sqlalchemy_repositories import SqlAlchemyRepositoryBundle


def _db_admin_headers(client: TestClient, username: str = "dbadmin", password: str = "dbadmin") -> dict[str, str]:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _reset_database_with_migrations(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture
def db_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    original_database_url = settings.database_url
    test_database_url = f"sqlite:///{(tmp_path / 'control_plane_test.db').as_posix()}"
    settings.database_url = test_database_url
    _reset_database_with_migrations(test_database_url)

    test_engine = create_engine(test_database_url, future=True, connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)
    original_init_engine = init_db_module.engine
    original_readiness_engine = readiness_module.engine
    init_db_module.engine = test_engine
    readiness_module.engine = test_engine

    session = TestSessionLocal()
    session.add(
        Host(
            id="host_db_01",
            agent_id="agent-db-01",
            hostname="db-host-01",
            fqdn="db-host-01.company.local",
            status="online",
            agent_token_hash=hash_agent_token("db-token"),
            registered_at=datetime(2026, 4, 9, 11, 0, 0, tzinfo=timezone.utc),
            last_seen_at=None,
        )
    )
    session.add(Group(id="grp_db", name="DB Group", description="Group from database"))
    session.add(HostGroupMembership(host_id="host_db_01", group_id="grp_db"))
    session.add(Playbook(id="pb_db", name="db-playbook", description="Playbook from database"))
    session.add(Playbook(id="pb_db_vpn", name="db-vpn-playbook", description="VPN playbook from database"))
    session.add(
        Artifact(
            id="art_db_01",
            playbook_id="pb_db",
            version="1.0.0",
            checksum=sha256_digest(b"db-playbook-content"),
            content_type="application/gzip",
            size_bytes=12,
            storage_path="artifacts/db-playbook-1.0.0.tar.gz",
        )
    )
    artifact_storage.write_bytes("artifacts/db-playbook-1.0.0.tar.gz", b"db-playbook-content")
    session.add(
        Artifact(
            id="art_db_vpn_01",
            playbook_id="pb_db_vpn",
            version="1.0.0",
            checksum=sha256_digest(b"db-vpn-playbook-content"),
            content_type="application/gzip",
            size_bytes=18,
            storage_path="artifacts/db-vpn-playbook-1.0.0.tar.gz",
        )
    )
    artifact_storage.write_bytes("artifacts/db-vpn-playbook-1.0.0.tar.gz", b"db-vpn-playbook-content")
    session.add(Policy(id="pol_db", name="DB Policy", description="Policy from database", priority=100, is_active=True))
    session.add(Policy(id="pol_db_group", name="DB Group Policy", description="Group policy from database", priority=200, is_active=True))
    session.add(PolicyAssignment(id="asg_db", policy_id="pol_db", target_type="global"))
    session.add(PolicyAssignment(id="asg_db_group", policy_id="pol_db_group", target_type="group", group_id="grp_db"))
    session.add(
        PolicyResource(
            id="res_db",
            policy_id="pol_db",
            type="ansible_playbook",
            playbook_id="pb_db",
            playbook_version="1.0.0",
            execution_order=10,
            variables={"x": 1},
            on_failure="stop",
        )
    )
    session.add(
        PolicyResource(
            id="res_db_group",
            policy_id="pol_db_group",
            type="ansible_playbook",
            playbook_id="pb_db_vpn",
            playbook_version="1.0.0",
            execution_order=20,
            variables={"vpn_server": "vpn.db.local"},
            on_failure="continue",
        )
    )
    session.add(
        InventorySnapshot(
            host_id="host_db_01",
            version=1,
            collected_at=datetime(2026, 4, 9, 11, 5, 0, tzinfo=timezone.utc),
            payload={"collected_at": "2026-04-09T11:05:00Z", "hostname": "db-host-01"},
        )
    )
    session.add(
        User(
            id="usr_db_admin_01",
            username="dbadmin",
            password_hash=hash_password("dbadmin"),
            role="admin",
            is_active=True,
            token_version=1,
        )
    )
    session.add(
        User(
            id="usr_db_auditor_01",
            username="dbauditor",
            password_hash=hash_password("dbauditor"),
            role="auditor",
            is_active=True,
            token_version=1,
        )
    )
    session.add(
        User(
            id="usr_db_operator_01",
            username="dboperator",
            password_hash=hash_password("dboperator"),
            role="operator",
            is_active=True,
            token_version=1,
        )
    )
    session.commit()
    session.close()

    def _service_override() -> Generator[ControlPlaneService, None, None]:
        db_session = TestSessionLocal()
        bundle = SqlAlchemyRepositoryBundle(db_session)
        try:
            yield ControlPlaneService(repository_bundle=bundle, seed_demo_data=False)
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    app.dependency_overrides[get_control_plane_service] = _service_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    init_db_module.engine = original_init_engine
    readiness_module.engine = original_readiness_engine
    settings.database_url = original_database_url
    test_engine.dispose()


def test_admin_hosts_list_from_database(db_client: TestClient) -> None:
    response = db_client.get("/api/v1/admin/hosts", headers=_db_admin_headers(db_client))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["host_id"] == "host_db_01"
    assert response.headers["x-request-id"]


def test_readinesscheck_on_database_backend(db_client: TestClient) -> None:
    response = db_client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["database"]["status"] == "ok"
    assert response.json()["checks"]["artifact_storage"]["status"] == "ok"


def test_admin_login_and_me_flow_on_database_backend(db_client: TestClient) -> None:
    login_response = db_client.post(
        "/api/v1/admin/auth/login",
        json={"username": "dbadmin", "password": "dbadmin"},
    )
    access_token = login_response.json()["access_token"]

    me_response = db_client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "dbadmin"
    assert me_response.json()["role"] == "admin"


def test_admin_refresh_logout_and_rbac_on_database_backend(db_client: TestClient) -> None:
    login_response = db_client.post(
        "/api/v1/admin/auth/login",
        json={"username": "dbadmin", "password": "dbadmin"},
    )
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = db_client.post(
        "/api/v1/admin/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    logout_response = db_client.post(
        "/api/v1/admin/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    revoked_me_response = db_client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    forbidden_write_response = db_client.post(
        "/api/v1/admin/groups",
        headers=_db_admin_headers(db_client, username="dbauditor", password="dbauditor"),
        json={"name": "Blocked DB Group", "description": "Should be forbidden"},
    )
    operator_create_response = db_client.post(
        "/api/v1/admin/groups",
        headers=_db_admin_headers(db_client, username="dboperator", password="dboperator"),
        json={"name": "Operator DB Group", "description": "Created by operator"},
    )
    operator_group_id = operator_create_response.json()["group_id"]
    operator_delete_response = db_client.delete(
        f"/api/v1/admin/groups/{operator_group_id}",
        headers=_db_admin_headers(db_client, username="dboperator", password="dboperator"),
    )

    assert refresh_response.status_code == 200
    assert logout_response.status_code == 204
    assert revoked_me_response.status_code == 401
    assert forbidden_write_response.status_code == 403
    assert operator_create_response.status_code == 201
    assert operator_delete_response.status_code == 403


def test_admin_policy_resources_list_from_database(db_client: TestClient) -> None:
    response = db_client.get("/api/v1/admin/policies/pol_db/resources", headers=_db_admin_headers(db_client))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["playbook_id"] == "pb_db"


def test_agent_artifact_metadata_from_database(db_client: TestClient) -> None:
    response = db_client.get(
        "/api/v1/agent/artifacts/art_db_01",
        headers={"Authorization": "Bearer db-token"},
    )

    assert response.status_code == 200
    assert response.json()["artifact_id"] == "art_db_01"


def test_agent_artifact_checksum_mismatch_from_database(db_client: TestClient) -> None:
    artifact_storage.write_bytes("artifacts/db-playbook-1.0.0.tar.gz", b"tampered")

    response = db_client.get(
        "/api/v1/agent/artifacts/art_db_01",
        headers={"Authorization": "Bearer db-token"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ARTIFACT_CHECKSUM_MISMATCH"


def test_agent_register_rejects_invalid_registration_token_on_database_backend(db_client: TestClient) -> None:
    response = db_client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-db-invalid-01",
            "registration_token": "wrong-token",
            "hostname": "db-invalid-01",
            "fqdn": "db-invalid-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.45"],
            "agent_version": "0.1.0",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REGISTRATION_TOKEN"


def test_agent_token_rotate_and_revoke_flow_on_database_backend(db_client: TestClient) -> None:
    admin_headers = _db_admin_headers(db_client)
    rotate_response = db_client.post(
        "/api/v1/admin/hosts/host_db_01/agent-token/rotate",
        headers=admin_headers,
    )
    new_token = rotate_response.json()["agent_token"]

    old_token_response = db_client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer db-token"},
    )
    new_token_response = db_client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    revoke_response = db_client.post(
        "/api/v1/admin/hosts/host_db_01/agent-token/revoke",
        headers=admin_headers,
    )
    revoked_token_response = db_client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    assert rotate_response.status_code == 200
    assert old_token_response.status_code == 401
    assert new_token_response.status_code == 200
    assert revoke_response.status_code == 204
    assert revoked_token_response.status_code == 401


def test_effective_policies_and_desired_state_from_database(db_client: TestClient) -> None:
    effective_response = db_client.get("/api/v1/admin/hosts/host_db_01/effective-policies", headers=_db_admin_headers(db_client))
    compliance_response = db_client.get("/api/v1/admin/hosts/host_db_01/compliance", headers=_db_admin_headers(db_client))
    state_response = db_client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer db-token"},
    )

    assert effective_response.status_code == 200
    assert compliance_response.status_code == 200
    assert compliance_response.json()["is_drifted"] is True
    assert compliance_response.json()["compliance_status"] == "pending_apply"
    assert len(effective_response.json()["items"]) == 2
    assert {item["scope"] for item in effective_response.json()["items"]} == {"global", "group"}
    assert state_response.status_code == 200
    assert len(state_response.json()["resources"]) == 2


def test_inventory_history_respects_retention_limit_on_database_backend(db_client: TestClient) -> None:
    register_response = db_client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-db-inventory-01",
            "registration_token": "bootstrap-secret",
            "hostname": "db-inventory-01",
            "fqdn": "db-inventory-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.48"],
            "agent_version": "0.1.0",
        },
    )
    auth = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}
    for version in range(1, 8):
        db_client.put(
            "/api/v1/agent/inventory",
            headers=auth,
            json={
                "collected_at": f"2026-04-09T12:2{version}:00Z",
                "os_name": "Ubuntu",
                "os_version": "24.04",
                "kernel_version": "6.8.0",
                "architecture": "x86_64",
                "hostname": "db-inventory-01",
                "fqdn": "db-inventory-01.company.local",
                "ip_addresses": ["10.10.1.48"],
                "memory_mb": 8192 + version,
                "disk": [],
                "extra": {"version": version},
            },
        )

    admin_headers = _db_admin_headers(db_client)
    latest_response = db_client.get(
        f"/api/v1/admin/hosts/{register_response.json()['host_id']}/inventory",
        headers=admin_headers,
    )
    history_response = db_client.get(
        f"/api/v1/admin/hosts/{register_response.json()['host_id']}/inventory/history",
        headers=admin_headers,
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["snapshot_version"] == 7
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 5
    assert history_response.json()["items"][0]["snapshot_version"] == 7
    assert history_response.json()["items"][-1]["snapshot_version"] == 3


def test_groups_crud_flow_on_database_backend(db_client: TestClient) -> None:
    admin_headers = _db_admin_headers(db_client)
    create_response = db_client.post(
        "/api/v1/admin/groups",
        headers=admin_headers,
        json={"name": "DB Support", "description": "Created in database"},
    )
    group_id = create_response.json()["group_id"]

    update_response = db_client.patch(
        f"/api/v1/admin/groups/{group_id}",
        headers=admin_headers,
        json={"description": "Updated in database"},
    )
    list_response = db_client.get("/api/v1/admin/groups", headers=admin_headers)
    delete_response = db_client.delete(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    missing_response = db_client.get(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    audit_response = db_client.get("/api/v1/admin/audit-log?entity_type=group", headers=admin_headers)

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert any(item["group_id"] == group_id for item in list_response.json()["items"])
    assert delete_response.status_code == 204
    assert missing_response.status_code == 404
    assert audit_response.status_code == 200
    assert [item["action"] for item in audit_response.json()["items"][:3]] == [
        "group.delete",
        "group.update",
        "group.create",
    ]


def test_policies_and_resources_flow_on_database_backend(db_client: TestClient) -> None:
    admin_headers = _db_admin_headers(db_client)
    create_policy = db_client.post(
        "/api/v1/admin/policies",
        headers=admin_headers,
        json={"name": "DB Created Policy", "priority": 250, "is_active": True},
    )
    policy_id = create_policy.json()["policy_id"]

    create_assignment = db_client.post(
        f"/api/v1/admin/policies/{policy_id}/assignments",
        headers=admin_headers,
        json={"target_type": "group", "target_id": "grp_db"},
    )
    create_resource = db_client.post(
        f"/api/v1/admin/policies/{policy_id}/resources",
        headers=admin_headers,
        json={
            "playbook_id": "pb_db",
            "playbook_version": "1.0.0",
            "execution_order": 40,
            "variables": {"db": True},
            "on_failure": "continue",
        },
    )
    resource_id = create_resource.json()["resource_id"]

    patch_resource = db_client.patch(
        f"/api/v1/admin/policies/{policy_id}/resources/{resource_id}",
        headers=admin_headers,
        json={"execution_order": 45},
    )
    list_resources = db_client.get(f"/api/v1/admin/policies/{policy_id}/resources", headers=admin_headers)

    assert create_policy.status_code == 201
    assert create_assignment.status_code == 201
    assert create_resource.status_code == 201
    assert patch_resource.status_code == 200
    assert patch_resource.json()["execution_order"] == 45
    assert list_resources.json()["total"] == 1


def test_playbooks_and_versions_flow_on_database_backend(db_client: TestClient) -> None:
    admin_headers = _db_admin_headers(db_client)
    create_playbook = db_client.post(
        "/api/v1/admin/playbooks",
        headers=admin_headers,
        json={"name": "db-created-playbook", "description": "Created in database"},
    )
    playbook_id = create_playbook.json()["playbook_id"]
    expected_checksum = sha256_digest(f"artifact:{playbook_id}:2.0.0".encode("utf-8"))

    create_version = db_client.post(
        f"/api/v1/admin/playbooks/{playbook_id}/versions",
        headers=admin_headers,
        json={"version": "2.0.0", "checksum": expected_checksum},
    )
    duplicate_version = db_client.post(
        f"/api/v1/admin/playbooks/{playbook_id}/versions",
        headers=admin_headers,
        json={"version": "2.0.0", "checksum": expected_checksum},
    )
    list_versions = db_client.get(f"/api/v1/admin/playbooks/{playbook_id}/versions", headers=admin_headers)

    assert create_playbook.status_code == 201
    assert create_version.status_code == 201
    assert duplicate_version.status_code == 409
    assert duplicate_version.json()["error"]["code"] == "PLAYBOOK_VERSION_ALREADY_EXISTS"
    assert list_versions.json()["total"] == 1


def test_playbook_version_rejects_checksum_mismatch_on_database_backend(db_client: TestClient) -> None:
    admin_headers = _db_admin_headers(db_client)
    create_playbook = db_client.post(
        "/api/v1/admin/playbooks",
        headers=admin_headers,
        json={"name": "db-checksum-test", "description": "Checksum validation"},
    )
    playbook_id = create_playbook.json()["playbook_id"]

    response = db_client.post(
        f"/api/v1/admin/playbooks/{playbook_id}/versions",
        headers=admin_headers,
        json={"version": "1.0.0", "checksum": "sha256:deadbeef"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ARTIFACT_CHECKSUM_MISMATCH"


def test_desired_state_conflict_on_database_backend(db_client: TestClient) -> None:
    admin_headers = _db_admin_headers(db_client)
    create_policy = db_client.post(
        "/api/v1/admin/policies",
        headers=admin_headers,
        json={"name": "DB Conflict Policy", "priority": 200, "is_active": True},
    )
    policy_id = create_policy.json()["policy_id"]

    db_client.post(
        f"/api/v1/admin/policies/{policy_id}/assignments",
        headers=admin_headers,
        json={"target_type": "group", "target_id": "grp_db"},
    )
    db_client.post(
        f"/api/v1/admin/policies/{policy_id}/resources",
        headers=admin_headers,
        json={
            "playbook_id": "pb_db_vpn",
            "playbook_version": "1.0.0",
            "execution_order": 20,
            "variables": {"vpn_server": "conflict.db.local"},
            "on_failure": "continue",
        },
    )

    response = db_client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer db-token"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFIGURATION_CONFLICT"


def test_agent_register_inventory_and_execution_flow_on_database_backend(db_client: TestClient) -> None:
    register_response = db_client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-db-flow-01",
            "registration_token": "bootstrap-secret",
            "hostname": "db-flow-01",
            "fqdn": "db-flow-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.44"],
            "agent_version": "0.1.0",
        },
    )
    token = register_response.json()["agent_token"]
    auth = {"Authorization": f"Bearer {token}"}
    desired_state_response = db_client.get(
        "/api/v1/agent/desired-state",
        headers=auth,
    )
    desired_revision = desired_state_response.json()["revision"]

    inventory_response = db_client.put(
        "/api/v1/agent/inventory",
        headers=auth,
        json={
            "collected_at": "2026-04-09T11:22:00Z",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "hostname": "db-flow-01",
            "fqdn": "db-flow-01.company.local",
            "ip_addresses": ["10.10.1.44"],
            "memory_mb": 4096,
            "disk": [],
            "extra": {},
        },
    )
    run_response = db_client.post(
        "/api/v1/agent/execution-runs",
        headers=auth,
        json={"state_revision": desired_revision, "started_at": "2026-04-09T11:23:00Z"},
    )
    run_id = run_response.json()["run_id"]
    events_response = db_client.post(
        f"/api/v1/agent/execution-runs/{run_id}/events",
        headers=auth,
        json={
            "reported_at": "2026-04-09T11:24:00Z",
            "items": [
                {
                    "resource_id": "res_base",
                    "artifact_id": "art_db_01",
                    "status": "success",
                    "started_at": "2026-04-09T11:23:10Z",
                    "finished_at": "2026-04-09T11:23:50Z",
                    "message": "Applied from database backend",
                }
            ],
        },
    )
    admin_headers = _db_admin_headers(db_client)
    runs_response = db_client.get("/api/v1/admin/execution-runs", headers=admin_headers)
    hosts_response = db_client.get("/api/v1/admin/hosts", headers=admin_headers)
    compliance_response = db_client.get(
        f"/api/v1/admin/hosts/{register_response.json()['host_id']}/compliance",
        headers=admin_headers,
    )

    assert register_response.status_code == 201
    assert inventory_response.status_code == 200
    assert run_response.status_code == 201
    assert events_response.status_code == 202
    assert runs_response.status_code == 200
    assert any(item["host_id"] == register_response.json()["host_id"] for item in hosts_response.json()["items"])
    assert any(item["run_id"] == run_id for item in runs_response.json()["items"])
    assert any(item["aggregate_status"] == "success" for item in runs_response.json()["items"] if item["run_id"] == run_id)
    assert compliance_response.status_code == 200
    assert compliance_response.json()["is_drifted"] is False
    assert compliance_response.json()["compliance_status"] == "in_sync"


def test_execution_runs_filter_by_failed_status_on_database_backend(db_client: TestClient) -> None:
    register_response = db_client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-db-failed-flow-01",
            "registration_token": "bootstrap-secret",
            "hostname": "db-failed-01",
            "fqdn": "db-failed-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.46"],
            "agent_version": "0.1.0",
        },
    )
    auth = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}
    run_response = db_client.post(
        "/api/v1/agent/execution-runs",
        headers=auth,
        json={"state_revision": 1, "started_at": "2026-04-09T11:23:00Z"},
    )
    db_client.post(
        f"/api/v1/agent/execution-runs/{run_response.json()['run_id']}/events",
        headers=auth,
        json={
            "reported_at": "2026-04-09T11:24:00Z",
            "items": [
                {
                    "resource_id": "res_base",
                    "artifact_id": "art_db_01",
                    "status": "failed",
                    "started_at": "2026-04-09T11:23:10Z",
                    "finished_at": "2026-04-09T11:23:50Z",
                    "message": "Failed from database backend",
                }
            ],
        },
    )

    response = db_client.get(
        "/api/v1/admin/execution-runs?status=failed",
        headers=_db_admin_headers(db_client),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["aggregate_status"] == "failed"


def test_execution_events_are_idempotent_by_event_id_on_database_backend(db_client: TestClient) -> None:
    register_response = db_client.post(
        "/api/v1/agent/register",
        json={
            "agent_id": "agent-db-idempotent-01",
            "registration_token": "bootstrap-secret",
            "hostname": "db-idempotent-01",
            "fqdn": "db-idempotent-01.company.local",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "ip_addresses": ["10.10.1.47"],
            "agent_version": "0.1.0",
        },
    )
    auth = {"Authorization": f"Bearer {register_response.json()['agent_token']}"}
    run_response = db_client.post(
        "/api/v1/agent/execution-runs",
        headers=auth,
        json={"state_revision": 1, "started_at": "2026-04-09T11:23:00Z"},
    )
    payload = {
        "reported_at": "2026-04-09T11:24:00Z",
        "items": [
            {
                "event_id": "evt-db-001",
                "resource_id": "res_base",
                "artifact_id": "art_db_01",
                "status": "success",
                "started_at": "2026-04-09T11:23:10Z",
                "finished_at": "2026-04-09T11:23:50Z",
                "message": "Applied from database backend",
            }
        ],
    }
    db_client.post(f"/api/v1/agent/execution-runs/{run_response.json()['run_id']}/events", headers=auth, json=payload)
    db_client.post(f"/api/v1/agent/execution-runs/{run_response.json()['run_id']}/events", headers=auth, json=payload)

    response = db_client.get("/api/v1/admin/execution-runs", headers=_db_admin_headers(db_client))

    assert response.status_code == 200
    matching_items = [item for item in response.json()["items"] if item["run_id"] == run_response.json()["run_id"]]
    assert matching_items[0]["events_count"] == 1
