import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User, RefreshToken, Workspace, UserRole, PasswordResetToken
from app.db.session import get_db, AsyncSessionLocal
from app.security.auth import (
    hash_password, verify_password, validate_password_strength,
    create_access_token, create_refresh_token, decode_access_token,
)

log = structlog.get_logger()
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin@company.com",
                "password": "StrongPassword@123",
                "full_name": "John Admin",
                "workspace_slug": "acme-tech",
                "company_name": "Acme Technologies",
            }
        }
    )

    email: EmailStr = Field(description="Admin email address.")
    password: str = Field(description="Strong password (uppercase, lowercase, number, special char).")
    full_name: str = Field(description="Admin full name.")
    workspace_slug: str = Field(description="Unique workspace identifier, e.g. `acme-tech`.")
    # Optional: human-readable company name stored as workspace.name
    company_name: Optional[str] = Field(default=None, description="Optional company name for display.")

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT access token.")
    refresh_token: str = Field(description="Refresh token used to obtain new access tokens.")
    token_type: str = Field(default="bearer", description="Token type used in Authorization header.")
    expires_in: int = Field(
        default=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        description="Access token expiry in seconds.",
    )


class UserResponse(BaseModel):
    id: uuid.UUID = Field(description="User UUID.")
    email: str = Field(description="User email.")
    full_name: Optional[str] = Field(default=None, description="User display name.")
    role: str = Field(description="User role.")
    workspace_id: uuid.UUID = Field(description="Workspace UUID.")


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "admin@company.com"}}
    )
    email: EmailStr = Field(description="Registered user email.")


class ForgotPasswordResponse(BaseModel):
    message: str = Field(description="Generic response to avoid account enumeration.")
    reset_token: Optional[str] = Field(
        default=None,
        description="Returned only in non-production for local testing.",
    )
    reset_url: Optional[str] = Field(
        default=None,
        description="Convenience URL returned only in non-production.",
    )


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "reset-token-from-forgot-password",
                "new_password": "StrongPassword@123",
            }
        }
    )
    token: str = Field(description="Password reset token.")
    new_password: str = Field(description="New strong password.")

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


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


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Register Workspace Admin",
    description=(
        "Creates a workspace (if needed), creates an admin user, and returns access + refresh tokens.\n\n"
        "Use this for first-time onboarding."
    ),
    response_description="Access and refresh tokens.",
)
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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login (OAuth2 form)",
    description=(
        "Authenticates a user using form fields `username` (email) and `password`.\n\n"
        "Content-Type must be `application/x-www-form-urlencoded`."
    ),
    response_description="Access and refresh tokens.",
)
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


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Generates a new access token (and refresh token) from a valid refresh token.",
    response_description="New token pair.",
)
async def refresh_tokens(
    refresh_token: str = Query(..., description="Refresh token returned by login/register.")
):
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


@router.post(
    "/logout",
    summary="Logout",
    description="Revokes the provided refresh token.",
    response_description="Logout confirmation.",
)
async def logout(
    refresh_token: str = Query(..., description="Refresh token to revoke.")
):
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
            stored = result.scalar_one_or_none()
            if stored:
                stored.revoked = True
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User",
    description="Returns profile and workspace context of the authenticated user.",
    response_description="Current user details.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        workspace_id=current_user.workspace_id,
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Start Password Reset",
    description=(
        "Creates a short-lived one-time password reset token for a registered active account.\n\n"
        "Response is intentionally generic to avoid exposing whether an email exists."
    ),
    response_description="Generic success message (and reset token in non-production).",
)
async def forgot_password(body: ForgotPasswordRequest):
    generic_message = "If that email is registered, password reset instructions are ready."
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(User).where(User.email == body.email, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            if not user:
                return ForgotPasswordResponse(message=generic_message)

            # Invalidate any previous unused tokens for this user.
            await db.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used == False,
                )
                .values(used=True, used_at=now)
            )

            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    used=False,
                )
            )

    if settings.ENVIRONMENT == "production":
        return ForgotPasswordResponse(message=generic_message)

    base = settings.FRONTEND_BASE_URL.rstrip("/")
    path = settings.PASSWORD_RESET_URL_PATH
    if not path.startswith("/"):
        path = f"/{path}"
    reset_url = f"{base}{path}?token={raw_token}"
    return ForgotPasswordResponse(message=generic_message, reset_token=raw_token, reset_url=reset_url)


@router.post(
    "/reset-password",
    summary="Complete Password Reset",
    description="Consumes a valid one-time token and updates the account password.",
    response_description="Password reset result.",
)
async def reset_password(body: ResetPasswordRequest):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            token_result = await db.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.token_hash == token_hash,
                    PasswordResetToken.used == False,
                    PasswordResetToken.expires_at > now,
                )
            )
            reset_token = token_result.scalar_one_or_none()
            if not reset_token:
                raise HTTPException(status_code=400, detail="Invalid or expired reset token")

            user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
            user = user_result.scalar_one_or_none()
            if not user or not user.is_active:
                raise HTTPException(status_code=400, detail="Invalid reset token")

            user.hashed_password = hash_password(body.new_password)
            user.updated_at = now
            reset_token.used = True
            reset_token.used_at = now

            # Revoke all active refresh tokens to force re-login everywhere.
            await db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked == False,
                )
                .values(revoked=True)
            )

    return {"message": "Password has been reset successfully. Please sign in again."}
