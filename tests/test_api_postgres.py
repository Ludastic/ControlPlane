from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_control_plane_service
from app.main import app
from app.models.artifact import Artifact
from app.models.group import Group, HostGroupMembership
from app.models.host import Host
from app.models.playbook import Playbook
from app.models.policy import Policy, PolicyAssignment, PolicyResource
from app.models.user import User
from app.core.security import hash_agent_token, hash_password
from app.repositories.sqlalchemy_repositories import SqlAlchemyRepositoryBundle
from app.services.artifact_storage import artifact_storage
from app.services.control_plane_service import ControlPlaneService


POSTGRES_TEST_URL = os.getenv("CONTROL_PLANE_POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="CONTROL_PLANE_POSTGRES_TEST_URL is not configured",
)


def _upgrade_postgres_database(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _postgres_admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "pgadmin", "password": "pgadmin"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pg_client() -> Generator[TestClient, None, None]:
    pytest.importorskip("psycopg")
    assert POSTGRES_TEST_URL is not None

    engine = create_engine(POSTGRES_TEST_URL, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    _upgrade_postgres_database(POSTGRES_TEST_URL)

    session = SessionLocal()
    session.add(
        Host(
            id="host_pg_01",
            agent_id="agent-pg-01",
            hostname="pg-host-01",
            fqdn="pg-host-01.company.local",
            status="online",
            agent_token_hash=hash_agent_token("pg-token"),
            registered_at=datetime(2026, 4, 9, 11, 0, 0, tzinfo=timezone.utc),
            last_seen_at=None,
        )
    )
    session.add(Group(id="grp_pg", name="PG Group", description="Group from postgres"))
    session.add(HostGroupMembership(host_id="host_pg_01", group_id="grp_pg"))
    session.add(Playbook(id="pb_pg", name="pg-playbook", description="Playbook from postgres"))
    session.add(
        Artifact(
            id="art_pg_01",
            playbook_id="pb_pg",
            version="1.0.0",
            checksum="sha256:pg123",
            content_type="application/gzip",
            size_bytes=12,
            storage_path="artifacts/pg-playbook-1.0.0.tar.gz",
        )
    )
    artifact_storage.write_bytes("artifacts/pg-playbook-1.0.0.tar.gz", b"pg-playbook-content")
    session.add(Policy(id="pol_pg", name="PG Policy", description="Policy from postgres", priority=100, is_active=True))
    session.add(PolicyAssignment(id="asg_pg", policy_id="pol_pg", target_type="global"))
    session.add(
        PolicyResource(
            id="res_pg",
            policy_id="pol_pg",
            type="ansible_playbook",
            playbook_id="pb_pg",
            playbook_version="1.0.0",
            execution_order=10,
            variables={"postgres": True},
            on_failure="stop",
        )
    )
    session.add(
        User(
            id="usr_pg_admin_01",
            username="pgadmin",
            password_hash=hash_password("pgadmin"),
            role="admin",
            is_active=True,
            token_version=1,
        )
    )
    session.commit()
    session.close()

    def _service_override() -> Generator[ControlPlaneService, None, None]:
        db_session = SessionLocal()
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
    engine.dispose()


def test_postgres_admin_and_agent_flow(pg_client: TestClient) -> None:
    headers = _postgres_admin_headers(pg_client)
    hosts_response = pg_client.get("/api/v1/admin/hosts", headers=headers)
    state_response = pg_client.get(
        "/api/v1/agent/desired-state",
        headers={"Authorization": "Bearer pg-token"},
    )

    assert hosts_response.status_code == 200
    assert hosts_response.json()["items"][0]["host_id"] == "host_pg_01"
    assert state_response.status_code == 200
    assert state_response.json()["resources"][0]["artifact"]["artifact_id"] == "art_pg_01"
