from __future__ import annotations

from pathlib import Path

from app.core.settings import settings


class LocalArtifactStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.artifacts_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, storage_path: str) -> Path:
        path = self.root / storage_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

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


artifact_storage = LocalArtifactStorage()
