from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.services.user_service import register_user, login_user, get_user_profile
from app.api.deps import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(payload: RegisterRequest):
    result, error = await register_user(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name or "",
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return result


@router.post("/login")
async def login(payload: LoginRequest):
    result, error = await login_user(
        email=payload.email,
        password=payload.password,
    )

    if error:
        raise HTTPException(status_code=401, detail=error)

    return result


@router.post("/token")
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2-compatible token endpoint for Swagger UI's 'Authorize' button.
    Swagger sends `username`/`password` as form data; we treat `username`
    as the email. Use /auth/login for normal JSON-based login from the
    frontend.
    """
    result, error = await login_user(
        email=form_data.username,
        password=form_data.password,
    )

    if error:
        raise HTTPException(status_code=401, detail=error)

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return await get_user_profile(current_user)