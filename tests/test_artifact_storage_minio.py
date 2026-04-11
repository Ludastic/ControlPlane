from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.core.settings import settings
from app.services.artifact_storage import S3ArtifactStorage


MINIO_TEST_ENDPOINT_URL = os.getenv("CONTROL_PLANE_MINIO_TEST_ENDPOINT_URL")
MINIO_TEST_BUCKET = os.getenv("CONTROL_PLANE_MINIO_TEST_BUCKET", "control-plane-test")
MINIO_TEST_ACCESS_KEY = os.getenv("CONTROL_PLANE_MINIO_TEST_ACCESS_KEY", "minioadmin")
MINIO_TEST_SECRET_KEY = os.getenv("CONTROL_PLANE_MINIO_TEST_SECRET_KEY", "minioadmin")
MINIO_TEST_REGION = os.getenv("CONTROL_PLANE_MINIO_TEST_REGION", "us-east-1")

pytestmark = pytest.mark.skipif(
    not MINIO_TEST_ENDPOINT_URL,
    reason="CONTROL_PLANE_MINIO_TEST_ENDPOINT_URL is not configured",
)


def test_s3_artifact_storage_against_minio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "artifact_storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_endpoint_url", MINIO_TEST_ENDPOINT_URL)
    monkeypatch.setattr(settings, "s3_bucket", MINIO_TEST_BUCKET)
    monkeypatch.setattr(settings, "s3_access_key", MINIO_TEST_ACCESS_KEY)
    monkeypatch.setattr(settings, "s3_secret_key", MINIO_TEST_SECRET_KEY)
    monkeypatch.setattr(settings, "s3_region", MINIO_TEST_REGION)

    storage = S3ArtifactStorage()
    storage_path = f"integration/{uuid4().hex}.tar.gz"
    payload = b"minio-artifact-content"

    health = storage.healthcheck()
    storage.write_bytes(storage_path, payload)

    try:
        assert health["status"] == "ok"
        assert health["backend"] == "s3"
        assert storage.exists(storage_path) is True
        assert storage.read_bytes(storage_path) == payload
        assert storage.size_bytes(storage_path) == len(payload)
        assert storage_path in storage.list_files()
    finally:
        storage.delete(storage_path)

    assert storage.exists(storage_path) is False
