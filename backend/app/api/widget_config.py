"""
app/api/widget_config.py
Admin endpoint to save widget configuration.
Add this router to main.py:
  from app.api import widget_config
  app.include_router(widget_config.router, prefix=f"{settings.API_PREFIX}/admin", tags=["admin"])
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.db.models import WidgetConfig, ApiKey
from app.db.session import get_db
from app.security.auth import generate_api_key

router = APIRouter()


class WidgetConfigRequest(BaseModel):
    bot_name: str = "Tissa"
    greeting_message: str = "Hi! How can I help you today?"
    primary_color: str = "#E65C5C"
    secondary_color: str = "#c0392b"
    placeholder_text: str = "Type a message..."
    avatar_url: Optional[str] = None
    position: str = "bottom-right"
    allowed_domains: list[str] = []


@router.post("/widget-api-key")
async def create_widget_api_key(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create and return a RAW widget API key for this workspace.

    This raw value must be embedded into the customer's website (as `data-bot-id`),
    and the frontend must send it back as `X-API-Key`.
    """
    raw_key, prefix, hashed = generate_api_key()

    api_key = ApiKey(
        workspace_id=admin.workspace_id,
        name="widget",
        key_hash=hashed,
        key_prefix=prefix,
        scopes=["widget", "chat"],
        is_active=True,
    )
    db.add(api_key)
    await db.commit()

    return {"api_key": raw_key, "prefix": prefix}


@router.post("/widget-config")
async def save_widget_config(
    body: WidgetConfigRequest,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Save or update widget configuration for the workspace."""
    result = await db.execute(
        select(WidgetConfig).where(
            WidgetConfig.workspace_id == admin.workspace_id,
            WidgetConfig.is_active == True,
        )
    )
    config = result.scalar_one_or_none()

    if config:
        config.bot_name = body.bot_name
        config.greeting_message = body.greeting_message
        config.primary_color = body.primary_color
        config.secondary_color = body.secondary_color
        config.placeholder_text = body.placeholder_text
        config.avatar_url = body.avatar_url
        config.position = body.position
        config.allowed_domains = body.allowed_domains
    else:
        config = WidgetConfig(
            workspace_id=admin.workspace_id,
            bot_name=body.bot_name,
            greeting_message=body.greeting_message,
            primary_color=body.primary_color,
            secondary_color=body.secondary_color,
            placeholder_text=body.placeholder_text,
            avatar_url=body.avatar_url,
            position=body.position,
            allowed_domains=body.allowed_domains,
        )
        db.add(config)

    await db.commit()
    return {
        "id": str(config.id),
        "bot_name": config.bot_name,
        "greeting_message": config.greeting_message,
        "primary_color": config.primary_color,
        "secondary_color": config.secondary_color,
        "placeholder_text": config.placeholder_text,
        "position": config.position,
    }
