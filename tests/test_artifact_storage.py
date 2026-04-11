from app.core.settings import settings
from app.services.artifact_storage import LocalArtifactStorage, S3ArtifactStorage, build_artifact_storage


def test_build_artifact_storage_returns_local_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "artifact_storage_backend", "local")

    storage = build_artifact_storage()

    assert isinstance(storage, LocalArtifactStorage)
    assert storage.identifier == "local"


def test_build_artifact_storage_returns_s3_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "artifact_storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_bucket", "playbooks")
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")

    storage = build_artifact_storage()

    assert isinstance(storage, S3ArtifactStorage)
    assert storage.identifier == "s3"


def test_local_artifact_storage_initialize_creates_root(tmp_path) -> None:
    storage = LocalArtifactStorage(root=tmp_path / "artifacts-root")

    storage.initialize()

    assert storage.root.exists()
    assert storage.root.is_dir()


def test_s3_artifact_storage_initialize_ensures_bucket(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.head_bucket_called = 0

        def head_bucket(self, Bucket: str) -> None:
            self.head_bucket_called += 1

    fake_client = FakeClient()

    monkeypatch.setattr(settings, "s3_bucket", "playbooks")
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")

    storage = S3ArtifactStorage()
    monkeypatch.setattr(storage, "_get_client", lambda: fake_client)

    storage.initialize()

    assert fake_client.head_bucket_called == 1
