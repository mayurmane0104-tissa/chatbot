import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User, RefreshToken, Workspace, UserRole
from app.db.session import get_db, AsyncSessionLocal
from app.security.auth import (
    hash_password, verify_password, validate_password_strength,
    create_access_token, create_refresh_token, decode_access_token,
)

log = structlog.get_logger()
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    workspace_slug: str
    # Optional: human-readable company name stored as workspace.name
    company_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    role: str
    workspace_id: uuid.UUID


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    err = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise err
    except Exception:
        raise err
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise err
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, request: Request):
    async with AsyncSessionLocal() as db:
        async with db.begin():
            slug = data.workspace_slug.lower().strip()

            if settings.ENFORCE_GLOBAL_UNIQUE_EMAIL:
                email_exists = await db.execute(
                    select(User).where(User.email == data.email)
                )
                if email_exists.scalar_one_or_none():
                    raise HTTPException(
                        status_code=409,
                        detail="Email already registered. Use a different email for another company workspace.",
                    )

            # Find or create workspace
            result = await db.execute(
                select(Workspace).where(Workspace.slug == slug)
            )
            workspace = result.scalar_one_or_none()
            if workspace and not settings.ALLOW_WORKSPACE_JOIN_ON_REGISTER:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Workspace slug '{slug}' already exists. "
                        "Use a unique workspace slug for a new company."
                    ),
                )

            if not workspace:
                workspace = Workspace(
                    name=data.company_name or slug,
                    slug=slug,
                    plan="free",
                    is_active=True,
                    settings={},
                )
                db.add(workspace)
                await db.flush()

            # Check duplicate email within this workspace
            result = await db.execute(
                select(User).where(User.workspace_id == workspace.id, User.email == data.email)
            )
            if result.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Email already registered")

            # Create user — is_verified=True immediately (no OTP)
            user = User(
                workspace_id=workspace.id,
                email=data.email,
                hashed_password=hash_password(data.password),
                full_name=data.full_name,
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,   # FIX: set verified immediately, OTP removed
            )
            db.add(user)
            await db.flush()

            # Issue tokens
            access_token = create_access_token(
                str(user.id),
                {"workspace_id": str(workspace.id), "role": user.role.value},
            )
            raw_refresh, hashed_refresh = create_refresh_token()
            db.add(RefreshToken(
                user_id=user.id,
                token_hash=hashed_refresh,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ))

    log.info("user.registered", email=data.email, workspace=slug)
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None):
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(select(User).where(User.email == form.username))
            user = result.scalar_one_or_none()

            if not user or not verify_password(form.password, user.hashed_password):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            if not user.is_active:
                raise HTTPException(status_code=403, detail="Account disabled")

            user.last_login_at = datetime.now(timezone.utc)

            access_token = create_access_token(
                str(user.id),
                {"workspace_id": str(user.workspace_id), "role": user.role.value},
            )
            raw_refresh, hashed_refresh = create_refresh_token()
            db.add(RefreshToken(
                user_id=user.id,
                token_hash=hashed_refresh,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ))

    log.info("user.login", email=form.username)
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(refresh_token: str):
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.revoked == False,
                    RefreshToken.expires_at > datetime.now(timezone.utc),
                )
            )
            stored = result.scalar_one_or_none()
            if not stored:
                raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

            stored.revoked = True
            user_result = await db.execute(select(User).where(User.id == stored.user_id))
            user = user_result.scalar_one()

            access_token = create_access_token(
                str(user.id),
                {"workspace_id": str(user.workspace_id), "role": user.role.value},
            )
            raw_refresh, hashed_refresh = create_refresh_token()
            db.add(RefreshToken(
                user_id=user.id,
                token_hash=hashed_refresh,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ))

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/logout")
async def logout(refresh_token: str):
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
            stored = result.scalar_one_or_none()
            if stored:
                stored.revoked = True
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        workspace_id=current_user.workspace_id,
    )
