from __future__ import annotations

import hashlib


def sha256_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def verify_sha256(content: bytes, expected_checksum: str) -> bool:
    return sha256_digest(content) == expected_checksum
