from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.errors import AppError
from app.core.settings import settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2_sha256$100000${salt}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    iterations = int(iterations_raw)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return hmac.compare_digest(derived.hex(), digest)


def hash_agent_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def extract_bearer_token(authorization: str | None, *, error_code: str, message: str) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise AppError(status_code=401, code=error_code, message=message)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AppError(status_code=401, code=error_code, message=message)
    return token


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _encode_token(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(
        settings.admin_jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{header_part}.{payload_part}.{_b64url_encode(signature)}"


def create_admin_token(*, subject: str, username: str, role: str, token_type: str, ttl_seconds: int, token_version: int) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "username": username,
        "role": role,
        "typ": token_type,
        "ver": token_version,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return _encode_token(payload)


def decode_admin_token(token: str, *, expected_type: str = "access") -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".")
    except ValueError as exc:
        raise AppError(status_code=401, code="INVALID_ADMIN_TOKEN", message="Invalid admin token") from exc

    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected_signature = hmac.new(
        settings.admin_jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_part)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise AppError(status_code=401, code="INVALID_ADMIN_TOKEN", message="Invalid admin token")

    try:
        payload = json.loads(_b64url_decode(payload_part))
    except json.JSONDecodeError as exc:
        raise AppError(status_code=401, code="INVALID_ADMIN_TOKEN", message="Invalid admin token") from exc

    if payload.get("typ") != expected_type:
        raise AppError(status_code=401, code="INVALID_ADMIN_TOKEN", message="Invalid admin token")
    if payload.get("exp", 0) < int(time.time()):
        raise AppError(status_code=401, code="ADMIN_TOKEN_EXPIRED", message="Admin token expired")
    return payload
