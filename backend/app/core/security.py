from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390000
JWT_ALGORITHM = "HS256"


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Invalid email format")
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, expected_hash_raw = password_hash.split("$", maxsplit=3)
        if algorithm != PBKDF2_ALGORITHM:
            return False

        iterations = int(iterations_raw)
        salt = _b64url_decode(salt_raw)
        expected_hash = _b64url_decode(expected_hash_raw)
    except (TypeError, ValueError):
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def create_access_token(
    *,
    subject: str,
    secret_key: str,
    expires_delta: timedelta,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if additional_claims:
        payload.update(additional_claims)

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    encoded_header = _json_b64url_encode(header)
    encoded_payload = _json_b64url_encode(payload)
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url_encode(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(*, token: str, secret_key: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", maxsplit=2)
    except ValueError as exc:
        raise ValueError("Invalid token") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Invalid token")

    header = _json_b64url_decode(encoded_header)
    if header.get("alg") != JWT_ALGORITHM:
        raise ValueError("Invalid token")

    payload = _json_b64url_decode(encoded_payload)
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("Invalid token")

    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    if exp <= now_ts:
        raise ValueError("Token expired")

    return payload


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _json_b64url_encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url_encode(raw)


def _json_b64url_decode(payload: str) -> dict[str, Any]:
    try:
        raw = _b64url_decode(payload)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid token") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid token")
    return data
