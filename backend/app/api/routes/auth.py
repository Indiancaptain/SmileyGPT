from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.core.token_revocation import is_token_revoked, revoke_token
from app.db.session import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    role = UserRole.admin if payload.email in settings.ADMIN_EMAILS else UserRole.user
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name or payload.email.split("@")[0],
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    if await is_token_revoked(decoded.get("jti", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has been revoked")

    result = await db.execute(select(User).where(User.id == decoded["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    # Rotate: the refresh token just used is single-use. If it were ever
    # replayed (e.g. stolen from storage and used after the legitimate
    # client already rotated it), this makes the replay fail instead of
    # silently minting another valid session.
    if decoded.get("jti") and decoded.get("exp"):
        await revoke_token(decoded["jti"], decoded["exp"])

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest | None = None, creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Revokes the access token used to authenticate this request, and —
    if provided — the refresh token as well, so a stolen token can't keep
    working after the legitimate user has logged out."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")

    decoded = decode_token(creds.credentials)
    if decoded and decoded.get("jti") and decoded.get("exp"):
        await revoke_token(decoded["jti"], decoded["exp"])

    if payload and payload.refresh_token:
        decoded_refresh = decode_token(payload.refresh_token)
        if decoded_refresh and decoded_refresh.get("jti") and decoded_refresh.get("exp"):
            await revoke_token(decoded_refresh["jti"], decoded_refresh["exp"])
