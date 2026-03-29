"""
app/api/widget.py
Public widget endpoints — no auth required, but workspace API key validated.
"""
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WidgetConfig, ApiKey, Workspace
from app.db.session import get_db
from app.security.auth import verify_api_key
from app.db.models import Conversation

router = APIRouter()


async def get_widget_workspace(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Validate API key and return workspace."""
    # Must match DB column size (api_keys.key_prefix is VARCHAR(10))
    prefix = x_api_key[:10] if len(x_api_key) >= 10 else ""

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.is_active == True,
        )
    )
    api_key = next(
        (
            candidate
            for candidate in result.scalars().all()
            if verify_api_key(x_api_key, candidate.key_hash)
        ),
        None,
    )

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    workspace_result = await db.execute(
        select(Workspace).where(Workspace.id == api_key.workspace_id, Workspace.is_active == True)
    )
    workspace = workspace_result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=403, detail="Workspace inactive")

    return workspace


@router.get("/config")
async def get_widget_config(
    workspace: Workspace = Depends(get_widget_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Return widget configuration for the frontend to render."""
    result = await db.execute(
        select(WidgetConfig).where(
            WidgetConfig.workspace_id == workspace.id,
            WidgetConfig.is_active == True,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        # Return defaults
        return {
            "bot_name": "Assistant",
            "greeting_message": "Hi! How can I help you today?",
            "primary_color": "#2563EB",
            "secondary_color": "#1E40AF",
            "placeholder_text": "Type your message...",
            "position": "bottom-right",
        }

    return {
        "bot_name": config.bot_name,
        "greeting_message": config.greeting_message,
        "primary_color": config.primary_color,
        "secondary_color": config.secondary_color,
        "placeholder_text": config.placeholder_text,
        "avatar_url": config.avatar_url,
        "position": config.position,
    }


@router.post("/session")
async def create_widget_session(
    request: Request,
    workspace: Workspace = Depends(get_widget_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Create an anonymous widget session."""
    from app.db.models import Session as DbSession
    from datetime import datetime, timedelta, timezone
    import secrets

    session_token = secrets.token_urlsafe(32)
    session = DbSession(
        session_token=session_token,
        workspace_id=workspace.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(session)
    return {"session_token": session_token}
