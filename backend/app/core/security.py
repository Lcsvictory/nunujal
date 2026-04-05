import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request as FastAPIRequest
from sqlalchemy.orm import Session

import app.models as models
from app.core.config import get_settings

settings = get_settings()


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def decode_jwt_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format.") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_b64):
        raise HTTPException(status_code=401, detail="Invalid token signature.")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token has expired.")

    return payload


def get_access_token_from_request(
    request: FastAPIRequest,
    authorization: str | None = None,
) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return request.cookies.get("access_token")


def get_authenticated_user(
    session: Session,
    request: FastAPIRequest,
    authorization: str | None = None,
) -> models.AppUser:
    token = get_access_token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    payload = decode_jwt_token(token)
    user = session.query(models.AppUser).filter(models.AppUser.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Authenticated user was not found.")

    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Inactive user cannot access this resource.")

    return user
