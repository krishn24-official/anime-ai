from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.services.user_service import (
    register_user,
    login_user,
    refresh_access_token,
    logout_user,
    logout_all_devices,
    get_user_profile,
    request_password_reset,
    verify_otp,
    reset_password,
)
from app.api.deps import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str


class LoginRequest(BaseModel):
    identifier: str     # email or username
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    confirm_password: str


# --- Register ---

@router.post("/register")
async def register(payload: RegisterRequest):
    result, error = await register_user(
        email=payload.email,
        password=payload.password,
        username=payload.username,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return result


# --- Login (JSON) ---

@router.post("/login")
async def login(payload: LoginRequest):
    result, error = await login_user(
        identifier=payload.identifier,
        password=payload.password,
    )

    if error:
        raise HTTPException(status_code=401, detail=error)

    return result


# --- Login (OAuth2 form — for Swagger Authorize button) ---

@router.post("/token")
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    result, error = await login_user(
        identifier=form_data.username,
        password=form_data.password,
    )

    if error:
        raise HTTPException(status_code=401, detail=error)

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
    }


# --- Refresh ---

@router.post("/refresh")
async def refresh(payload: RefreshRequest):
    """Exchange a valid refresh token for a new access token + rotated refresh token."""
    result, error = await refresh_access_token(payload.refresh_token)

    if error:
        raise HTTPException(status_code=401, detail=error)

    return result


# --- Logout (single device) ---

@router.post("/logout")
async def logout(payload: LogoutRequest):
    """Revoke the provided refresh token (logout current device)."""
    await logout_user(payload.refresh_token)
    return {"message": "Logged out successfully"}


# --- Logout all devices ---

@router.post("/logout-all")
async def logout_all(current_user: dict = Depends(get_current_user)):
    """Revoke all refresh tokens for the current user (logout all devices)."""
    await logout_all_devices(current_user["_id"])
    return {"message": "Logged out from all devices"}


# --- Me ---

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return await get_user_profile(current_user)


# --- Forgot Password ---

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    await request_password_reset(payload.email)
    return {
        "message": (
            "If this email is registered, an OTP has been sent. "
            "It expires in 10 minutes."
        )
    }


# --- Verify OTP ---

@router.post("/verify-otp")
async def verify_otp_endpoint(payload: VerifyOTPRequest):
    valid, error = await verify_otp(payload.email, payload.otp)

    if not valid:
        raise HTTPException(status_code=400, detail=error)

    return {"message": "OTP verified. You can now reset your password."}


# --- Reset Password ---

@router.post("/reset-password")
async def reset_password_endpoint(payload: ResetPasswordRequest):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    success, error = await reset_password(
        email=payload.email,
        otp=payload.otp,
        new_password=payload.new_password,
    )

    if not success:
        raise HTTPException(status_code=400, detail=error)

    return {"message": "Password reset successfully. You can now log in."}