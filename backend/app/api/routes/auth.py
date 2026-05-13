import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

import app.models as models
from app.core.config import get_settings
from app.core.security import get_authenticated_user
from app.database import get_session

router = APIRouter()
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


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


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
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


def _delete_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
    response.delete_cookie("session", path="/")


def _hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_jwt_token(user: models.AppUser, auth_session: models.AuthSession) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "sid": str(auth_session.id),
        "type": "access",
        "email": user.email,
        "provider": user.provider,
        "status": user.status,
        "iat": now,
        "exp": now + (settings.access_token_expire_minutes * 60),
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _client_ip(request: FastAPIRequest) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host[:64]
    return None


def _create_login_session(
    session: Session,
    user: models.AppUser,
    request: FastAPIRequest,
) -> tuple[models.AuthSession, str]:
    now = datetime.now()
    session.query(models.AuthSession).filter(
        models.AuthSession.user_id == user.id,
        models.AuthSession.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)

    refresh_token = _new_refresh_token()
    auth_session = models.AuthSession(
        user_id=user.id,
        refresh_token_hash=_hash_refresh_token(refresh_token),
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(auth_session)
    session.flush()
    return auth_session, refresh_token


def _get_valid_refresh_session(session: Session, refresh_token: str | None) -> models.AuthSession:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token is required.")

    auth_session = (
        session.query(models.AuthSession)
        .filter(models.AuthSession.refresh_token_hash == _hash_refresh_token(refresh_token))
        .first()
    )
    now = datetime.now()
    if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Session has expired or was revoked.")

    if auth_session.user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Inactive user cannot refresh this session.")

    return auth_session


def _serialize_user(user: models.AppUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_image_url": user.profile_image_url,
    }


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
        auth_session, refresh_token = _create_login_session(session, user, request)
        session.commit()
        session.refresh(user)
        session.refresh(auth_session)
        session_user = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "provider": user.provider,
        }
        access_token = create_jwt_token(user, auth_session)
    except HTTPException as exc:
        session.rollback()
        return RedirectResponse(
            url=_frontend_redirect_url("/login", auth="error", message=str(exc.detail)),
            status_code=302,
        )
    except Exception as exc:
        session.rollback()
        return RedirectResponse(
            url=_frontend_redirect_url("/login", auth="error", message="Failed to create login session."),
            status_code=302,
        )
    finally:
        session.close()

    request.session.pop("google_oauth_state", None)
    request.session["user"] = session_user

    response = RedirectResponse(
        url=_frontend_redirect_url(
            "/projects",
            auth="success",
            message="Login successful",
        ),
        status_code=302,
    )
    _set_auth_cookies(response, access_token, refresh_token)
    return response

# For testing purposes only - do not use in production
@router.get("/logined-leader", summary="For testing: log in as a dummy leader user without Google OAuth")
def login_as_dummy_leader(request: FastAPIRequest) -> RedirectResponse:
    return for_test_token_cookie_return("dummy_google_leader_001", request)

@router.get("/logined-member", summary="For testing: log in as a dummy member user without Google OAuth")
def login_as_dummy_member(request: FastAPIRequest) -> RedirectResponse:
    return for_test_token_cookie_return("dummy_google_member_001", request)


@router.get("/logined-{user_name}", summary="For testing: log in as a user by name without Google OAuth")
def login_as_dummy_user_by_name(user_name: str, request: FastAPIRequest) -> RedirectResponse:
    return for_test_token_cookie_return_by_name(user_name, request)


def for_test_token_cookie_return(id: str, request: FastAPIRequest) -> RedirectResponse:
    session = get_session()
    try:
        user = session.query(models.AppUser).filter(models.AppUser.provider_user_id == id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Test user not found.")
        if user.status != "ACTIVE":
            raise HTTPException(status_code=403, detail=f"User is not active. status={user.status}")
        user.last_login_at = datetime.now()
        auth_session, refresh_token = _create_login_session(session, user, request)
        session.commit()
        session.refresh(user)
        session.refresh(auth_session)
        access_token = create_jwt_token(user, auth_session)
    except Exception as exc:
        session.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Database error or user not found.") from exc
    finally:
        session.close()

    response = RedirectResponse(
        url=_frontend_redirect_url(
            "/projects",
            auth="success",
            message="Login successful",
        ),
        status_code=302,
    )
    _set_auth_cookies(response, access_token, refresh_token)
    return response


def for_test_token_cookie_return_by_name(user_name: str, request: FastAPIRequest) -> RedirectResponse:
    normalized_name = user_name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="User name is required.")

    session = get_session()
    try:
        users = (
            session.query(models.AppUser)
            .filter(models.AppUser.name == normalized_name)
            .all()
        )
        if not users:
            raise HTTPException(status_code=404, detail="Test user not found.")
        if len(users) > 1:
            raise HTTPException(status_code=409, detail="Multiple users have the same name.")

        user = users[0]
        if user.status != "ACTIVE":
            raise HTTPException(status_code=403, detail=f"User is not active. status={user.status}")

        user.last_login_at = datetime.now()
        auth_session, refresh_token = _create_login_session(session, user, request)
        session.commit()
        session.refresh(user)
        session.refresh(auth_session)

        access_token = create_jwt_token(user, auth_session)
    except Exception as exc:
        session.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Database error or user not found.") from exc
    finally:
        session.close()

    response = RedirectResponse(
        url=_frontend_redirect_url(
            "/projects",
            auth="success",
            message="Login successful",
        ),
        status_code=302,
    )
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.get("/me", summary="Current authenticated user")
def read_current_user(
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    session = get_session()
    try:
        try:
            user = get_authenticated_user(session, request, authorization)
        except HTTPException:
            if not authorization and not request.cookies.get(ACCESS_TOKEN_COOKIE):
                return JSONResponse({"authenticated": False, "user": None})
            raise

        return JSONResponse(
            {
                "authenticated": True,
                "user": _serialize_user(user),
            }
        )
    finally:
        session.close()


@router.post("/refresh", summary="Refresh current access token")
def refresh_current_session(request: FastAPIRequest) -> JSONResponse:
    session = get_session()
    try:
        auth_session = _get_valid_refresh_session(session, request.cookies.get(REFRESH_TOKEN_COOKIE))
        user = auth_session.user
        now = datetime.now()
        new_refresh_token = _new_refresh_token()
        auth_session.refresh_token_hash = _hash_refresh_token(new_refresh_token)
        auth_session.last_used_at = now
        auth_session.expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        session.commit()
        session.refresh(user)
        session.refresh(auth_session)
        access_token = create_jwt_token(user, auth_session)

        response = JSONResponse({"ok": True, "user": _serialize_user(user)})
        _set_auth_cookies(response, access_token, new_refresh_token)
        return response
    except HTTPException as exc:
        session.rollback()
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        _delete_auth_cookies(response)
        return response
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to refresh session.") from exc
    finally:
        session.close()


@router.post("/logout", summary="Clear current session")
def logout(request: FastAPIRequest) -> JSONResponse:
    request.session.pop("user", None)
    request.session.pop("google_oauth_state", None)
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_token:
        session = get_session()
        try:
            auth_session = (
                session.query(models.AuthSession)
                .filter(models.AuthSession.refresh_token_hash == _hash_refresh_token(refresh_token))
                .first()
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = datetime.now()
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    response = JSONResponse({"ok": True})
    _delete_auth_cookies(response)
    return response
