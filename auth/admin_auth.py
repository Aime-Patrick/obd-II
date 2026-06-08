"""Admin access — JWT (dashboard login) or API key (scripts / legacy)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import verify_token
from config.database import get_database
from config.settings import settings
from services import admin_key_service

_bearer = HTTPBearer(auto_error=False)


async def verify_admin_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
    db=Depends(get_database),
) -> dict:
    """Accept Bearer JWT (role=admin) or X-Admin-API-Key."""
    if credentials and credentials.credentials:
        payload = verify_token(credentials.credentials)
        if payload and payload.get("role") == "admin":
            request.state.admin_user_id = payload.get("sub")
            request.state.admin_key_id = None
            request.state.admin_key_bootstrap = False
            return payload
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session.",
        )

    db_count = await db.admin_api_keys.count_documents({})

    if db_count == 0:
        bootstrap = (settings.ADMIN_BOOTSTRAP_KEY or settings.ADMIN_API_KEY or "").strip()
        if bootstrap:
            if x_admin_api_key == bootstrap:
                request.state.admin_user_id = None
                request.state.admin_key_id = None
                request.state.admin_key_bootstrap = True
                return {"bootstrap": True, "role": "api_key"}
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bootstrap admin API key.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )

    if not x_admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )

    doc = await admin_key_service.validate_key(db, x_admin_api_key)
    request.state.admin_user_id = None
    request.state.admin_key_id = str(doc["_id"])
    request.state.admin_key_bootstrap = False
    return {"role": "api_key", "sub": str(doc["_id"])}


def get_admin_key_id(request: Request) -> str | None:
    return getattr(request.state, "admin_key_id", None)
