from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from models.user import UserCreate, UserLogin, UserResponse
from auth.password_utils import hash_password, verify_password
from auth.jwt_handler import create_access_token
from config.database import get_database
from services.email_service import email_service
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import secrets
import string

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user: UserCreate, 
    background_tasks: BackgroundTasks,
    db=Depends(get_database)
):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_dict = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "full_name": user.full_name,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_dict)
    user_dict["_id"] = result.inserted_id
    
    # Send Welcome Email
    background_tasks.add_task(
        email_service.send_welcome_email,
        user.email,
        user.full_name
    )
    
    return UserResponse(
        id=str(result.inserted_id),
        email=user.email,
        full_name=user.full_name,
        created_at=user_dict["created_at"]
    )

@router.post("/login")
async def login(user: UserLogin, db=Depends(get_database)):
    # Find user
    db_user = await db.users.find_one({"email": user.email})
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create token
    access_token = create_access_token({"sub": str(db_user["_id"]), "email": db_user["email"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user["_id"]),
            "email": db_user["email"],
            "full_name": db_user["full_name"]
        }
    }


# ── Password Reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


def _generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_database),
):
    """Generate a 6-digit OTP and email it. Always returns 200 to avoid user enumeration."""
    user = await db.users.find_one({"email": body.email})
    if user:
        otp = _generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        await db.password_resets.update_one(
            {"email": body.email},
            {"$set": {"otp": otp, "expires_at": expires_at, "used": False}},
            upsert=True,
        )
        background_tasks.add_task(
            email_service.send_password_reset_otp,
            body.email,
            otp,
        )
    return {"message": "If that email exists, a reset code has been sent."}


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(body: VerifyOtpRequest, db=Depends(get_database)):
    """Verify the OTP is valid and not expired (does NOT consume it yet)."""
    record = await db.password_resets.find_one({"email": body.email})
    if (
        not record
        or record.get("used")
        or record.get("otp") != body.otp
        or record.get("expires_at") < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )
    return {"message": "Code verified."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: ResetPasswordRequest, db=Depends(get_database)):
    """Verify OTP one final time, update password, mark OTP used."""
    record = await db.password_resets.find_one({"email": body.email})
    if (
        not record
        or record.get("used")
        or record.get("otp") != body.otp
        or record.get("expires_at") < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )
    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 6 characters.",
        )
    await db.users.update_one(
        {"email": body.email},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.utcnow()}},
    )
    await db.password_resets.update_one(
        {"email": body.email}, {"$set": {"used": True}}
    )
    return {"message": "Password reset successfully."}
