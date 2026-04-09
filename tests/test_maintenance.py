from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.repositories.in_memory import InMemoryRepository
from app.repositories.sqlalchemy_repositories import SqlAlchemyRepositoryBundle
from app.services.artifact_storage import artifact_storage
from app.services.maintenance import MaintenanceService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_cleanup_service_prunes_orphans_and_old_history_in_memory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(artifact_storage, "root", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
    repo = InMemoryRepository(now)
    service = MaintenanceService(repo)

    artifact_storage.write_bytes("seed/base-config-1.0.0.tar.gz", b"seed")
    artifact_storage.write_bytes("cleanup/orphan.tar.gz", b"orphan")

    repo.execution.save(
        "run_old",
        {
            "host_id": "host_demo_01",
            "state_revision": 1,
            "started_at": now - timedelta(days=settings.execution_retention_days + 1),
            "reported_at": now,
            "events": [],
        },
    )
    repo.execution.save(
        "run_recent",
        {
            "host_id": "host_demo_01",
            "state_revision": 2,
            "started_at": now - timedelta(days=1),
            "reported_at": now,
            "events": [],
        },
    )
    repo.audit_logs.save(
        {
            "audit_id": "aud_old",
            "actor_user_id": "usr_admin_01",
            "actor_username": "admin",
            "action": "test.old",
            "entity_type": "test",
            "entity_id": "old",
            "details": None,
            "created_at": now - timedelta(days=settings.audit_retention_days + 1),
        }
    )
    repo.audit_logs.save(
        {
            "audit_id": "aud_recent",
            "actor_user_id": "usr_admin_01",
            "actor_username": "admin",
            "action": "test.recent",
            "entity_type": "test",
            "entity_id": "recent",
            "details": None,
            "created_at": now - timedelta(days=1),
        }
    )

    summary = service.cleanup(now=now)

    assert summary.orphan_artifact_files_deleted == 1
    assert summary.execution_runs_deleted == 1
    assert summary.audit_logs_deleted == 1
    assert artifact_storage.exists("seed/base-config-1.0.0.tar.gz")
    assert not artifact_storage.exists("cleanup/orphan.tar.gz")
    assert repo.execution.get("run_old") is None
    assert repo.execution.get("run_recent") is not None
    assert len(repo.audit_logs.list_all()) == 1
    assert repo.audit_logs.list_all()[0]["audit_id"] == "aud_recent"


def test_cleanup_service_prunes_orphans_and_old_history_in_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(artifact_storage, "root", tmp_path / "artifacts")
    artifact_storage.root.mkdir(parents=True, exist_ok=True)

    database_path = tmp_path / "cleanup.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _alembic_config(database_url)
    original_database_url = settings.database_url
    settings.database_url = database_url
    try:
        command.upgrade(config, "head")

        engine = create_engine(database_url, future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        session = Session()
        try:
            repo = SqlAlchemyRepositoryBundle(session)
            now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)

            repo.playbooks.save({"playbook_id": "pb_cleanup", "name": "cleanup", "description": "cleanup"})
            repo.artifacts.save(
                {
                    "artifact_id": "art_cleanup",
                    "name": "cleanup",
                    "playbook_id": "pb_cleanup",
                    "version": "1.0.0",
                    "checksum": "sha256:abc123",
                    "content_type": "application/gzip",
                    "size_bytes": 3,
                    "storage_path": "referenced/cleanup.tar.gz",
                }
            )
            artifact_storage.write_bytes("referenced/cleanup.tar.gz", b"ref")
            artifact_storage.write_bytes("orphan/orphan.tar.gz", b"orphan")

            repo.execution.save(
                "run_old",
                {
                    "host_id": "host_x",
                    "state_revision": 1,
                    "started_at": now - timedelta(days=settings.execution_retention_days + 2),
                    "reported_at": now,
                    "events": [],
                },
            )
            repo.execution.save(
                "run_recent",
                {
                    "host_id": "host_x",
                    "state_revision": 2,
                    "started_at": now - timedelta(days=1),
                    "reported_at": now,
                    "events": [],
                },
            )
            repo.audit_logs.save(
                {
                    "audit_id": "aud_old",
                    "actor_user_id": "usr_admin_01",
                    "actor_username": "admin",
                    "action": "cleanup.old",
                    "entity_type": "cleanup",
                    "entity_id": "old",
                    "details": None,
                    "created_at": now - timedelta(days=settings.audit_retention_days + 2),
                }
            )
            repo.audit_logs.save(
                {
                    "audit_id": "aud_recent",
                    "actor_user_id": "usr_admin_01",
                    "actor_username": "admin",
                    "action": "cleanup.recent",
                    "entity_type": "cleanup",
                    "entity_id": "recent",
                    "details": None,
                    "created_at": now - timedelta(days=1),
                }
            )

            summary = MaintenanceService(repo).cleanup(now=now)
            session.commit()

            assert summary.orphan_artifact_files_deleted == 1
            assert summary.execution_runs_deleted == 1
            assert summary.audit_logs_deleted == 1
            assert artifact_storage.exists("referenced/cleanup.tar.gz")
            assert not artifact_storage.exists("orphan/orphan.tar.gz")
            assert repo.execution.get("run_old") is None
            assert repo.execution.get("run_recent") is not None
            assert len(repo.audit_logs.list_all()) == 1
            assert repo.audit_logs.list_all()[0]["audit_id"] == "aud_recent"
        finally:
            session.close()
            engine.dispose()
    finally:
        settings.database_url = original_database_url
