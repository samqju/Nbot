"""Authentication helpers for the V3 Observation control plane."""

from __future__ import annotations

import hmac


MIN_CONTROL_TOKEN_LENGTH = 32


def validate_control_token(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("NBOT_CONTROL_AUTH_TOKEN_INVALID")
    token = value.strip()
    if token != value or len(token) < MIN_CONTROL_TOKEN_LENGTH or len(token) > 512:
        raise ValueError("NBOT_CONTROL_AUTH_TOKEN_INVALID")
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in token):
        raise ValueError("NBOT_CONTROL_AUTH_TOKEN_INVALID")
    return token


def bearer_header(token: str) -> str:
    return f"Bearer {validate_control_token(token)}"


def authorized(*, token: str, authorization_header: str | None) -> bool:
    expected = bearer_header(token)
    return hmac.compare_digest(str(authorization_header or ""), expected)
