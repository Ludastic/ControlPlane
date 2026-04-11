from __future__ import annotations

from app.services.artifact_storage import artifact_storage


def initialize_runtime_components() -> None:
    artifact_storage.initialize()
