from datetime import datetime, timedelta, timezone

from app.repositories.user_repository import (
    get_user_by_email,
    get_user_by_username,
    get_user_by_email_or_username,
    get_user_by_id,
    create_user,
    set_otp,
    clear_otp,
    update_password,
)
from app.repositories.refresh_token_repository import (
    save_refresh_token,
    get_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_otp,
    verify_otp_hash,
)
from app.services.email_service import generate_otp, send_otp_email
from app.config import OTP_EXPIRE_MINUTES


def _serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "username": user.get("username"),
        "display_name": user.get("display_name"),
    }


def _auth_response(user: dict, access_token: str, refresh_token: str) -> dict:
    return {
        "user": _serialize_user(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 900,   # 15 minutes in seconds
    }


async def _issue_tokens(user: dict) -> tuple[str, str]:
    """Issue access + refresh token pair for a user."""
    access_token = create_access_token(str(user["_id"]), user["email"])
    refresh_token, expires_at = create_refresh_token()
    await save_refresh_token(user["_id"], refresh_token, expires_at)
    return access_token, refresh_token


async def register_user(email: str, password: str, username: str):

    if await get_user_by_email(email):
        return None, "Email already registered"

    if await get_user_by_username(username):
        return None, "Username already taken"

    if len(password) < 6:
        return None, "Password must be at least 6 characters"

    if len(username) < 3:
        return None, "Username must be at least 3 characters"

    if not username.replace("_", "").replace(".", "").isalnum():
        return None, "Username can only contain letters, numbers, underscores and dots"

    user = await create_user(
        email=email,
        hashed_password=hash_password(password),
        username=username,
    )

    access_token, refresh_token = await _issue_tokens(user)

    return _auth_response(user, access_token, refresh_token), None


async def login_user(identifier: str, password: str):
    user = await get_user_by_email_or_username(identifier)

    if not user or not verify_password(password, user["password_hash"]):
        return None, "Invalid email/username or password"

    access_token, refresh_token = await _issue_tokens(user)

    return _auth_response(user, access_token, refresh_token), None


async def refresh_access_token(refresh_token_str: str):
    """Validate refresh token and issue a new access token.
    Also rotates the refresh token (old one revoked, new one issued)."""

    token_doc = await get_refresh_token(refresh_token_str)

    if not token_doc:
        return None, "Invalid or revoked refresh token"

    # Check expiry
    expires_at = token_doc["expires_at"]
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        await revoke_refresh_token(refresh_token_str)
        return None, "Refresh token expired. Please log in again"

    # Fetch user
    user = await get_user_by_id(str(token_doc["user_id"]))
    if not user:
        return None, "User not found"

    # Rotate: revoke old token, issue new pair
    await revoke_refresh_token(refresh_token_str)
    access_token, new_refresh_token = await _issue_tokens(user)

    return _auth_response(user, access_token, new_refresh_token), None


async def logout_user(refresh_token_str: str):
    """Revoke the specific refresh token (single device logout)."""
    await revoke_refresh_token(refresh_token_str)


async def logout_all_devices(user_id):
    """Revoke all refresh tokens for the user."""
    await revoke_all_user_tokens(user_id)


async def get_user_profile(user: dict) -> dict:
    return _serialize_user(user)


async def request_password_reset(email: str):
    user = await get_user_by_email(email)

    if not user:
        return True, None  # Don't reveal whether email exists

    otp = generate_otp()
    otp_hash = hash_otp(otp)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)

    await set_otp(email, otp_hash, expires_at)
    await send_otp_email(
        to_email=email,
        otp=otp,
        display_name=user.get("display_name", ""),
    )

    return True, None


async def verify_otp(email: str, otp: str):
    user = await get_user_by_email(email)

    if not user:
        return False, "Email not found"

    stored_hash = user.get("otp_hash")
    expires_at = user.get("otp_expires_at")

    if not stored_hash or not expires_at:
        return False, "No OTP requested for this email"

    now = datetime.now(timezone.utc)
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        await clear_otp(email)
        return False, "OTP has expired. Please request a new one"

    if not verify_otp_hash(otp, stored_hash):
        return False, "Invalid OTP"

    return True, None


async def reset_password(email: str, otp: str, new_password: str):
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters"

    valid, error = await verify_otp(email, otp)
    if not valid:
        return False, error

    await update_password(email, hash_password(new_password))
    await clear_otp(email)

    # Revoke all existing refresh tokens after password reset
    user = await get_user_by_email(email)
    if user:
        await revoke_all_user_tokens(user["_id"])

    return True, None