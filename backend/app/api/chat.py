"""
app/api/chat.py  — FIXED VERSION
Key fixes:
1. Bedrock session created correctly even without a prior conversation
2. All errors now log the real exception so you can see what is failing
3. SSE stream properly closed on error
4. DB session handled cleanly for async streaming
"""
import json
import re
import uuid
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.metrics import chat_errors_total, chat_messages_total, user_feedback_total
from app.db.models import (
    ApiKey,
    Conversation, Message, MessageFeedback,
    MessageRole, FeedbackType, Workspace
)
from app.db.session import get_db, AsyncSessionLocal
from app.security.auth import verify_api_key

log = structlog.get_logger()
router = APIRouter()

INJECTION_PATTERNS = [
    r"ignore (previous|all|above) instructions",
    r"you are now",
    r"forget everything",
    r"new instructions:",
    r"jailbreak",
    r"DAN mode",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


class SendMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_profile: Optional["UserProfilePayload"] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > settings.MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message too long (max {settings.MAX_MESSAGE_LENGTH} chars)")
        return v


class FeedbackRequest(BaseModel):
    feedback_type: FeedbackType
    comment: Optional[str] = None


class UserProfilePayload(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    industry: Optional[str] = None
    role: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_string_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


SendMessageRequest.model_rebuild()


def sse(data: dict, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _merged_profile(profile: Optional[UserProfilePayload], metadata: dict) -> dict:
    existing = metadata.get("user_profile")
    existing_profile = existing if isinstance(existing, dict) else {}
    incoming = profile.model_dump(exclude_none=True) if profile else {}
    return {**existing_profile, **incoming}


async def _resolve_user_and_workspace(
    request: Request,
    db: AsyncSession,
) -> tuple[Optional[uuid.UUID], uuid.UUID]:
    user_id: Optional[uuid.UUID] = None
    workspace_id: Optional[uuid.UUID] = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.security.auth import decode_access_token
            payload = decode_access_token(auth_header[7:])
            user_id = uuid.UUID(payload["sub"])
            workspace_id = uuid.UUID(payload["workspace_id"])
        except Exception as e:
            log.debug("chat.auth_parse_failed", error=str(e))

    # For embedded widget calls (no JWT), resolve workspace from X-API-Key.
    if workspace_id is None:
        x_api_key = request.headers.get("X-API-Key")
        if x_api_key:
            prefix = x_api_key[:10] if len(x_api_key) >= 10 else ""
            api_key_result = await db.execute(
                select(ApiKey).where(
                    ApiKey.key_prefix == prefix,
                    ApiKey.is_active == True,
                )
            )
            api_key = next(
                (
                    candidate
                    for candidate in api_key_result.scalars().all()
                    if verify_api_key(x_api_key, candidate.key_hash)
                ),
                None,
            )
            if not api_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
            workspace_id = api_key.workspace_id

    if workspace_id is None:
        raise HTTPException(status_code=401, detail="Missing workspace context")

    return user_id, workspace_id


@router.post("/message")
async def send_message(
    body: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if INJECTION_RE.search(body.message):
        log.warning("chat.injection_attempt")
        chat_errors_total.labels(error_type="injection_blocked").inc()
        async def blocked():
            yield sse({"content": "I am sorry, I cannot process that request."})
            yield sse({}, event="end")
        return StreamingResponse(blocked(), media_type="text/event-stream")

    user_id, workspace_id = await _resolve_user_and_workspace(request, db)

    # Workspace-specific Bedrock configuration.
    # Admins can store: bedrock_agent_id, bedrock_agent_alias_id, bedrock_kb_id in `workspaces.settings`.
    bedrock_agent_id: Optional[str] = None
    bedrock_agent_alias_id: Optional[str] = None
    bedrock_knowledge_base_id: Optional[str] = None
    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.is_active == True)
    )
    ws = ws_result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=403, detail="Workspace inactive or not found")

    settings_json = ws.settings if isinstance(ws.settings, dict) else {}
    bedrock_agent_id = settings_json.get("bedrock_agent_id") or None
    bedrock_agent_alias_id = settings_json.get("bedrock_agent_alias_id") or None
    bedrock_knowledge_base_id = settings_json.get("bedrock_kb_id") or None
    if bedrock_agent_id and not bedrock_knowledge_base_id:
        raise HTTPException(
            status_code=503,
            detail="Workspace knowledge base is not configured for isolated retrieval",
        )

    session_id = body.session_id or str(uuid.uuid4())

    # Get or create conversation
    conversation: Optional[Conversation] = None
    if body.conversation_id:
        try:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == uuid.UUID(body.conversation_id),
                    Conversation.workspace_id == workspace_id,
                )
            )
            conversation = result.scalar_one_or_none()
        except Exception:
            pass

    if not conversation:
        conversation = Conversation(
            workspace_id=workspace_id,
            user_id=user_id,
            session_id=session_id,
            bedrock_session_id=str(uuid.uuid4()),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(conversation)
        await db.flush()

    # Persist role/profile in DB metadata so it can drive future suggestions.
    metadata = conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
    merged_profile = _merged_profile(body.user_profile, metadata)
    if merged_profile:
        metadata["user_profile"] = merged_profile
        role_value = merged_profile.get("role")
        if isinstance(role_value, str) and role_value.strip():
            metadata["role"] = role_value.strip().lower()
        conversation.metadata_ = metadata

    profile_for_prompt = metadata.get("user_profile") if isinstance(metadata.get("user_profile"), dict) else None

    bedrock_session = conversation.bedrock_session_id
    conv_id = conversation.id
    conv_id_str = str(conv_id)

    # Save user message and commit before streaming
    user_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content=body.message,
    )
    db.add(user_msg)
    await db.commit()
    chat_messages_total.labels(role="user").inc()

    log.info("chat.message_received", conversation_id=conv_id_str, session=bedrock_session)

    async def stream_response():
        full_response = ""
        metadata: dict = {}
        assistant_msg_id = str(uuid.uuid4())

        try:
            from app.agents.bedrock_client import bedrock_client

            async for chunk in bedrock_client.invoke_agent_streaming(
                user_message=body.message,
                session_id=bedrock_session,
                agent_id=bedrock_agent_id,
                agent_alias_id=bedrock_agent_alias_id,
                knowledge_base_id=bedrock_knowledge_base_id,
                workspace_id=str(workspace_id),
                user_profile=profile_for_prompt,
            ):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    yield sse({"content": chunk["content"], "conversation_id": conv_id_str})

                elif chunk["type"] == "end":
                    metadata = chunk.get("metadata", {})
                    # Persist assistant message in a fresh session
                    async with AsyncSessionLocal() as save_db:
                        async with save_db.begin():
                            am = Message(
                                id=uuid.UUID(assistant_msg_id),
                                conversation_id=conv_id,
                                role=MessageRole.ASSISTANT,
                                content=full_response or "(empty response)",
                                tokens_used=metadata.get("tokens_used"),
                                latency_ms=metadata.get("latency_ms"),
                                model_id=metadata.get("model_id"),
                            )
                            save_db.add(am)
                            result = await save_db.execute(
                                select(Conversation).where(Conversation.id == conv_id)
                            )
                            conv = result.scalar_one_or_none()
                            if conv:
                                conv.message_count = (conv.message_count or 0) + 2
                                if not conv.title:
                                    conv.title = body.message[:100]
                    chat_messages_total.labels(role="assistant").inc()
                    yield sse({"message_id": assistant_msg_id, "conversation_id": conv_id_str, **metadata}, event="end")

                elif chunk["type"] == "error":
                    log.error("chat.bedrock_error_chunk", content=chunk.get("content"))
                    chat_errors_total.labels(error_type="bedrock_error").inc()
                    yield sse({"content": chunk["content"]})
                    yield sse({"conversation_id": conv_id_str}, event="end")

        except Exception as e:
            log.error("chat.stream_exception", error=str(e), exc_info=True)
            chat_errors_total.labels(error_type="stream_exception").inc()
            yield sse({"content": "Sorry, I encountered an error. Please try again."})
            yield sse({"conversation_id": conv_id_str}, event="end")

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/suggestions")
async def get_role_suggestions(
    role: str,
    request: Request,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    normalized_role = role.strip().lower()
    if not normalized_role:
        return {"role": "", "suggestions": []}

    _, workspace_id = await _resolve_user_and_workspace(request, db)
    safe_limit = max(1, min(limit, 10))
    query_window = safe_limit * 8

    result = await db.execute(
        select(Message.content)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.workspace_id == workspace_id,
            Message.role == MessageRole.USER,
            func.lower(
                func.coalesce(
                    Conversation.metadata_["role"].astext,
                    Conversation.metadata_["user_profile"]["role"].astext,
                    "",
                )
            ) == normalized_role,
        )
        .order_by(Message.created_at.desc())
        .limit(query_window)
    )

    suggestions: list[str] = []
    seen: set[str] = set()
    for content in result.scalars().all():
        text = (content or "").strip()
        if len(text) < 3:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(text)
        if len(suggestions) >= safe_limit:
            break

    return {"role": normalized_role, "suggestions": suggestions}


@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    return []


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    _, workspace_id = await _resolve_user_and_workspace(request, db)
    msgs = await db.execute(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.conversation_id == conv_uuid,
            Conversation.workspace_id == workspace_id,
        )
        .order_by(Message.created_at)
    )
    return [{"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in msgs.scalars().all()]


@router.post("/messages/{message_id}/feedback")
async def submit_feedback(
    message_id: str,
    body: FeedbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    try:
        msg_uuid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message ID")
    _, workspace_id = await _resolve_user_and_workspace(request, db)
    result = await db.execute(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == msg_uuid,
            Conversation.workspace_id == workspace_id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    db.add(MessageFeedback(message_id=msg_uuid, feedback_type=body.feedback_type, comment=body.comment))
    await db.commit()
    user_feedback_total.labels(type=body.feedback_type.value).inc()
    return {"success": True}
