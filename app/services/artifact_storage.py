from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.errors import AppError
from app.core.settings import settings


class ArtifactStorage(Protocol):
    identifier: str

    def initialize(self) -> None: ...

    def write_bytes(self, storage_path: str, content: bytes): ...

    def ensure_bytes(self, storage_path: str, content: bytes): ...

    def read_bytes(self, storage_path: str) -> bytes: ...

    def size_bytes(self, storage_path: str) -> int: ...

    def exists(self, storage_path: str) -> bool: ...

    def delete(self, storage_path: str) -> bool: ...

    def list_files(self) -> list[str]: ...

    def healthcheck(self) -> dict: ...


class LocalArtifactStorage:
    identifier = "local"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.artifacts_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, storage_path: str) -> Path:
        path = self.root / storage_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, storage_path: str, content: bytes) -> Path:
        path = self.resolve(storage_path)
        path.write_bytes(content)
        return path

    def ensure_bytes(self, storage_path: str, content: bytes) -> Path:
        path = self.resolve(storage_path)
        if not path.exists():
            path.write_bytes(content)
        return path

    def read_bytes(self, storage_path: str) -> bytes:
        return self.resolve(storage_path).read_bytes()

    def size_bytes(self, storage_path: str) -> int:
        return self.resolve(storage_path).stat().st_size

    def exists(self, storage_path: str) -> bool:
        return self.resolve(storage_path).exists()

    def delete(self, storage_path: str) -> bool:
        path = self.resolve(storage_path)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_files(self) -> list[str]:
        if not self.root.exists():
            return []
        return [
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
        ]

    def healthcheck(self) -> dict:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe_path = self.resolve(".healthcheck")
            probe_path.write_bytes(b"ok")
            probe_path.unlink(missing_ok=True)
            return {"status": "ok", "backend": self.identifier, "root": str(self.root)}
        except Exception as exc:
            return {"status": "failed", "backend": self.identifier, "error": str(exc)}


class S3ArtifactStorage:
    identifier = "s3"

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        if not self.bucket:
            raise AppError(status_code=503, code="INVALID_RUNTIME_CONFIGURATION", message="S3 bucket is not configured")
        self.endpoint_url = settings.s3_endpoint_url
        self.region = settings.s3_region
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise AppError(status_code=503, code="ARTIFACT_STORAGE_NOT_AVAILABLE", message="boto3 is required for S3 artifact storage") from exc
        session = boto3.session.Session()
        self._client = session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=self.region,
            config=Config(s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}),
        )
        return self._client

    def _ensure_bucket(self) -> None:
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.bucket)
        except Exception:
            params = {"Bucket": self.bucket}
            if self.region and self.region != "us-east-1":
                params["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            client.create_bucket(**params)

    def write_bytes(self, storage_path: str, content: bytes) -> str:
        self._ensure_bucket()
        self._get_client().put_object(Bucket=self.bucket, Key=storage_path, Body=content)
        return storage_path

    def initialize(self) -> None:
        self._ensure_bucket()

    def ensure_bytes(self, storage_path: str, content: bytes) -> str:
        if not self.exists(storage_path):
            self.write_bytes(storage_path, content)
        return storage_path

    def read_bytes(self, storage_path: str) -> bytes:
        response = self._get_client().get_object(Bucket=self.bucket, Key=storage_path)
        return response["Body"].read()

    def size_bytes(self, storage_path: str) -> int:
        response = self._get_client().head_object(Bucket=self.bucket, Key=storage_path)
        return int(response["ContentLength"])

    def exists(self, storage_path: str) -> bool:
        try:
            self._get_client().head_object(Bucket=self.bucket, Key=storage_path)
            return True
        except Exception:
            return False

    def delete(self, storage_path: str) -> bool:
        if not self.exists(storage_path):
            return False
        self._get_client().delete_object(Bucket=self.bucket, Key=storage_path)
        return True

    def list_files(self) -> list[str]:
        self._ensure_bucket()
        paginator = self._get_client().get_paginator("list_objects_v2")
        items: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket):
            for item in page.get("Contents", []):
                items.append(item["Key"])
        return items

    def healthcheck(self) -> dict:
        try:
            self._ensure_bucket()
            self._get_client().list_objects_v2(Bucket=self.bucket, MaxKeys=1)
            return {
                "status": "ok",
                "backend": self.identifier,
                "bucket": self.bucket,
                "endpoint_url": self.endpoint_url,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "backend": self.identifier,
                "bucket": self.bucket,
                "endpoint_url": self.endpoint_url,
                "error": str(exc),
            }


def build_artifact_storage() -> ArtifactStorage:
    backend = settings.artifact_storage_backend.lower()
    if backend == "local":
        return LocalArtifactStorage()
    if backend == "s3":
        return S3ArtifactStorage()
    raise AppError(status_code=503, code="INVALID_RUNTIME_CONFIGURATION", message=f"Unsupported artifact storage backend: {backend}")


artifact_storage = build_artifact_storage()
