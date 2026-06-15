from app.repositories.user_repository import (
    get_user_by_email,
    create_user,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)


def _serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "display_name": user.get("display_name"),
    }


async def register_user(email: str, password: str, display_name: str = ""):
    existing = await get_user_by_email(email)

    if existing:
        return None, "Email already registered"

    if len(password) < 6:
        return None, "Password must be at least 6 characters"

    user = await create_user(
        email=email,
        hashed_password=await hash_password(password),
        display_name=display_name,
    )

    token = create_access_token(str(user["_id"]), user["email"])

    return {"user": _serialize_user(user), "access_token": token, "token_type": "bearer"}, None


async def login_user(email: str, password: str):
    user = await get_user_by_email(email)

    if not user or not await verify_password(password, user["password_hash"]):
        return None, "Invalid email or password"

    token = create_access_token(str(user["_id"]), user["email"])

    return {"user": _serialize_user(user), "access_token": token, "token_type": "bearer"}, None


async def get_user_profile(user: dict) -> dict:
    return _serialize_user(user)