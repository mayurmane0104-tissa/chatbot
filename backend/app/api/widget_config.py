"""
app/api/widget_config.py
Admin endpoints to manage widget configuration and deployment snippet.
"""
import re
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.core.config import settings
from app.db.models import WidgetConfig, ApiKey
from app.db.session import get_db
from app.security.auth import generate_api_key

router = APIRouter()


def _generate_widget_public_id() -> str:
    # Keep only URL-safe alphanumerics and cap length.
    token = re.sub(r"[^a-zA-Z0-9]", "", secrets.token_urlsafe(24))
    return f"wid_{token[:24]}"


async def _new_unique_widget_public_id(db: AsyncSession) -> str:
    for _ in range(8):
        candidate = _generate_widget_public_id()
        exists = await db.execute(
            select(WidgetConfig.id).where(WidgetConfig.widget_public_id == candidate)
        )
        if not exists.scalar_one_or_none():
            return candidate
    raise RuntimeError("Unable to generate unique widget public id")


async def _get_or_create_active_widget_config(
    db: AsyncSession,
    workspace_id,
) -> WidgetConfig:
    result = await db.execute(
        select(WidgetConfig).where(
            WidgetConfig.workspace_id == workspace_id,
            WidgetConfig.is_active == True,
        )
    )
    config = result.scalar_one_or_none()
    if config:
        if not config.widget_public_id:
            config.widget_public_id = await _new_unique_widget_public_id(db)
        return config

    config = WidgetConfig(
        workspace_id=workspace_id,
        bot_name="Tissa",
        greeting_message="Hi! How can I help you today?",
        primary_color="#E65C5C",
        secondary_color="#c0392b",
        placeholder_text="Type a message...",
        position="bottom-right",
        allowed_domains=[],
        is_active=True,
        widget_public_id=await _new_unique_widget_public_id(db),
    )
    db.add(config)
    await db.flush()
    return config


def _resolve_widget_base_url(request: Request) -> str:
    configured = settings.WIDGET_PUBLIC_BASE_URL.strip()
    if configured:
        return configured.rstrip("/")
    origin = request.headers.get("origin", "").strip()
    if origin:
        return origin.rstrip("/")
    return str(request.base_url).rstrip("/")


def _resolve_api_base_url(request: Request) -> str:
    configured = settings.API_PUBLIC_BASE_URL.strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


class WidgetConfigRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bot_name": "Tissa",
                "greeting_message": "Hi! How can I help you today?",
                "primary_color": "#E65C5C",
                "secondary_color": "#c0392b",
                "placeholder_text": "Type a message...",
                "avatar_url": None,
                "position": "bottom-right",
                "allowed_domains": ["https://example.com"],
            }
        }
    )
    bot_name: str = Field(default="Tissa", description="Bot display name in widget header.")
    greeting_message: str = Field(default="Hi! How can I help you today?", description="Initial bot greeting.")
    primary_color: str = Field(default="#E65C5C", description="Primary hex color for widget.")
    secondary_color: str = Field(default="#c0392b", description="Secondary hex color for widget.")
    placeholder_text: str = Field(default="Type a message...", description="Input placeholder text.")
    avatar_url: Optional[str] = Field(default=None, description="Optional avatar image URL.")
    position: str = Field(default="bottom-right", description="Widget position, e.g. bottom-right.")
    allowed_domains: list[str] = Field(default_factory=list, description="Allowed host domains for embedding.")


@router.get(
    "/widget-config",
    summary="Get Admin Widget Configuration",
    description="Returns current widget configuration for the admin workspace.",
    response_description="Widget configuration payload.",
)
async def get_widget_config_admin(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_or_create_active_widget_config(db, admin.workspace_id)
    await db.commit()
    return {
        "id": str(config.id),
        "bot_name": config.bot_name,
        "greeting_message": config.greeting_message,
        "primary_color": config.primary_color,
        "secondary_color": config.secondary_color,
        "placeholder_text": config.placeholder_text,
        "avatar_url": config.avatar_url,
        "position": config.position,
        "allowed_domains": config.allowed_domains or [],
        "widget_public_id": config.widget_public_id,
    }


@router.post(
    "/widget-api-key",
    summary="Create Widget API Key (Legacy)",
    description=(
        "Generates a legacy raw API key for widget embedding. "
        "New installs should use widget public id deployment script."
    ),
    response_description="Raw API key and prefix.",
)
async def create_widget_api_key(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    raw_key, prefix, hashed = generate_api_key()

    # Keep only one active legacy widget key to reduce confusion.
    await db.execute(
        update(ApiKey)
        .where(
            ApiKey.workspace_id == admin.workspace_id,
            ApiKey.name == "widget",
            ApiKey.is_active == True,
        )
        .values(is_active=False)
    )

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


@router.post(
    "/widget-config",
    summary="Save Widget Configuration",
    description="Creates or updates widget UI settings for the admin workspace.",
    response_description="Saved widget configuration.",
)
async def save_widget_config(
    body: WidgetConfigRequest,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_or_create_active_widget_config(db, admin.workspace_id)

    config.bot_name = body.bot_name
    config.greeting_message = body.greeting_message
    config.primary_color = body.primary_color
    config.secondary_color = body.secondary_color
    config.placeholder_text = body.placeholder_text
    config.avatar_url = body.avatar_url
    config.position = body.position
    config.allowed_domains = body.allowed_domains

    await db.commit()
    return {
        "id": str(config.id),
        "bot_name": config.bot_name,
        "greeting_message": config.greeting_message,
        "primary_color": config.primary_color,
        "secondary_color": config.secondary_color,
        "placeholder_text": config.placeholder_text,
        "avatar_url": config.avatar_url,
        "position": config.position,
        "allowed_domains": config.allowed_domains or [],
        "widget_public_id": config.widget_public_id,
    }


@router.get(
    "/widget-deployment-script",
    summary="Get Deployment Script",
    description="Returns a copy-paste widget script for the current workspace.",
    response_description="Script tag and related deployment values.",
)
async def get_widget_deployment_script(
    request: Request,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_or_create_active_widget_config(db, admin.workspace_id)
    widget_id = config.widget_public_id or await _new_unique_widget_public_id(db)
    if not config.widget_public_id:
        config.widget_public_id = widget_id

    widget_base_url = _resolve_widget_base_url(request)
    api_base_url = _resolve_api_base_url(request)
    script_tag = (
        f'<script src="{widget_base_url}/embed.js" '
        f'data-bot-id="{widget_id}" '
        f'data-base-url="{widget_base_url}" '
        f'data-api-url="{api_base_url}" '
        "defer></script>"
    )
    await db.commit()
    return {
        "widget_id": widget_id,
        "widget_base_url": widget_base_url,
        "api_base_url": api_base_url,
        "script_tag": script_tag,
    }
