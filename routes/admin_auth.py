"""Admin dashboard login — JWT with role=admin."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from auth.jwt_handler import create_access_token
from auth.admin_auth import verify_admin_access
from config.database import get_database
from config.settings import settings
from services.admin_user_service import authenticate_admin

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])


class AdminLoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def admin_login(body: AdminLoginBody, db=Depends(get_database)):
    admin = await authenticate_admin(db, body.email, body.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(
        {
            "sub": str(admin["_id"]),
            "email": admin["email"],
            "role": "admin",
        },
        expires_minutes=settings.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "admin": {
            "id": str(admin["_id"]),
            "email": admin["email"],
            "full_name": admin.get("full_name", "Admin"),
        },
    }


@router.get("/me")
async def admin_me(admin=Depends(verify_admin_access)):
    if admin.get("role") == "admin":
        return {
            "id": admin.get("sub"),
            "email": admin.get("email"),
            "full_name": "Admin",
            "auth_type": "jwt",
        }
    return {"auth_type": "api_key"}
