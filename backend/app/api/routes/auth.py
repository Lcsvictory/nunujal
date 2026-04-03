import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker

import app.models as models
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def get_engine():
    return create_engine(settings.database_url)


def get_session() -> Session:
    session_factory = sessionmaker(bind=get_engine())
    return session_factory()


def _frontend_redirect_url(path: str, *, auth: str | None = None, message: str | None = None) -> str:
    query_params: dict[str, str] = {}
    if auth:
        query_params["auth"] = auth
    if message:
        query_params["message"] = message

    base_url = f"{settings.frontend_url.rstrip('/')}{path}"
    if not query_params:
        return base_url

    return f"{base_url}?{urlencode(query_params, quote_via=quote)}"


def _set_auth_cookie(response: RedirectResponse, jwt_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


def _require_google_oauth_config() -> None:
    if settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri:
        return

    raise HTTPException(
        status_code=503,
        detail="Google OAuth settings are missing. Configure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI.",
    )


def _request_json(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(url, data=data, headers=headers or {})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_jwt_token(user: models.AppUser) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "provider": user.provider,
        "status": user.status,
        "iat": now,
        "exp": now + (settings.jwt_expire_minutes * 60),
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


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


def _upsert_google_user(session: Session, user_info: dict[str, Any]) -> models.AppUser:
    provider_user_id = user_info.get("sub")
    email = user_info.get("email")

    if not provider_user_id or not email:
        raise HTTPException(status_code=400, detail="Google user info is missing required fields.")

    if user_info.get("email_verified") is False:
        raise HTTPException(status_code=403, detail="Google email is not verified.")

    user = (
        session.query(models.AppUser)
        .filter(
            or_(
                (models.AppUser.provider == "GOOGLE") & (models.AppUser.provider_user_id == provider_user_id),
                models.AppUser.email == email,
            )
        )
        .first()
    )

    if user is None:
        user = models.AppUser(
            provider="GOOGLE",
            provider_user_id=provider_user_id,
            email=email,
            name=user_info.get("name") or email.split("@")[0],
            profile_image_url=user_info.get("picture"),
            status="ACTIVE",
            last_login_at=datetime.now(),
        )
        session.add(user)
    else:
        user.provider = "GOOGLE"
        user.provider_user_id = provider_user_id
        user.email = email
        user.name = user_info.get("name") or user.name
        user.profile_image_url = user_info.get("picture")
        user.last_login_at = datetime.now()

    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"User is not allowed to log in. status={user.status}")

    session.commit()
    session.refresh(user)
    return user


@router.get("/google/login", summary="Start Google login")
def start_google_login(request: FastAPIRequest) -> RedirectResponse:
    _require_google_oauth_config()

    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state

    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
    )

    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}", status_code=302)


@router.get("/google/callback", summary="Handle Google callback")
def handle_google_callback(
    request: FastAPIRequest,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    _require_google_oauth_config()

    if error:
        return RedirectResponse(
            url=_frontend_redirect_url("/login", auth="error", message=f"Google login failed: {error}"),
            status_code=302,
        )

    saved_state = request.session.get("google_oauth_state")
    if not code or not state or not saved_state or state != saved_state:
        return RedirectResponse(
            url=_frontend_redirect_url("/login", auth="error", message="Invalid OAuth state."),
            status_code=302,
        )

    token_payload = urlencode(
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    try:
        token_response = _request_json(
            GOOGLE_TOKEN_URL,
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        access_token = token_response["access_token"]
        user_info = _request_json(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except (HTTPError, URLError, KeyError, json.JSONDecodeError) as exc:
        return RedirectResponse(
            url=_frontend_redirect_url(
                "/login",
                auth="error",
                message="Failed to exchange Google OAuth token.",
            ),
            status_code=302,
        )

    session = get_session()
    try:
        user = _upsert_google_user(session, user_info)
    except HTTPException as exc:
        return RedirectResponse(
            url=_frontend_redirect_url("/login", auth="error", message=str(exc.detail)),
            status_code=302,
        )
    finally:
        session.close()

    request.session.pop("google_oauth_state", None)
    request.session["user"] = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
    }

    jwt_token = create_jwt_token(user)
    response = RedirectResponse(
        url=_frontend_redirect_url(
            "/projects/select",
            auth="success",
            message="Login successful. Project selection page is not implemented yet.",
        ),
        status_code=302,
    )
    _set_auth_cookie(response, jwt_token)
    return response


@router.get("/me", summary="Current authenticated user")
def read_current_user(
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    else:
        token = request.cookies.get("access_token")

    if not token:
        return JSONResponse({"authenticated": False, "user": None})

    payload = decode_jwt_token(token)

    session = get_session()
    try:
        user = session.query(models.AppUser).filter(models.AppUser.id == int(payload["sub"])).first()
        if user is None:
            return JSONResponse({"authenticated": False, "user": None})

        return JSONResponse(
            {
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "provider": user.provider,
                    "profile_image_url": user.profile_image_url,
                    "status": user.status,
                },
            }
        )
    finally:
        session.close()


@router.post("/logout", summary="Clear current session")
def logout(request: FastAPIRequest) -> JSONResponse:
    request.session.pop("user", None)
    request.session.pop("google_oauth_state", None)
    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token", path="/")
    return response
