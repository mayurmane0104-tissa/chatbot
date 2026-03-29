"""
app/api/admin.py
Admin endpoints: analytics, conversations, documents, crawl pipeline.
"""
import uuid
import os
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from threading import Lock, Thread
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.core.config import settings
from app.db.models import (
    Conversation, Message, MessageFeedback, Document,
    DocumentStatus, FeedbackType, Workspace,
)
from app.db.session import get_db

log = structlog.get_logger()
router = APIRouter()

_LOCAL_CRAWL_TASKS: dict[str, dict[str, Optional[str]]] = {}
_LOCAL_CRAWL_TASKS_LOCK = Lock()


def _set_local_task_state(task_id: str, state: str, error: Optional[str] = None) -> None:
    with _LOCAL_CRAWL_TASKS_LOCK:
        _LOCAL_CRAWL_TASKS[task_id] = {"state": state, "error": error}


def _get_local_task_state(task_id: str) -> Optional[dict[str, Optional[str]]]:
    with _LOCAL_CRAWL_TASKS_LOCK:
        task = _LOCAL_CRAWL_TASKS.get(task_id)
    return dict(task) if task else None


def _has_live_celery_worker() -> bool:
    try:
        from app.workers.tasks import celery_app
        inspector = celery_app.control.inspect(timeout=0.8)
        pings = inspector.ping() if inspector else None
        return bool(pings)
    except Exception as exc:
        log.warning("crawl.worker_ping_failed", error=str(exc))
        return False


def _run_crawl_locally(task_id: str, workspace_id: str, url: str, max_pages: int) -> None:
    from app.workers.tasks import crawl_and_train

    _set_local_task_state(task_id, "STARTED")
    try:
        # On Windows, run the crawl in a separate process so Playwright (which needs
        # subprocess support in the event loop) can run reliably.
        if os.name == "nt":
            payload = json.dumps({
                "workspace_id": workspace_id,
                "url": url,
                "max_pages": max_pages,
            })
            code = (
                "import json, sys; "
                "from app.workers.tasks import crawl_and_train; "
                "p = json.loads(sys.argv[1]); "
                "res = crawl_and_train.apply("
                "args=[p['workspace_id'], p['url'], p['max_pages']], "
                "kwargs={'allow_retry': False}, "
                "throw=False"
                "); "
                "state = getattr(res, 'state', 'UNKNOWN'); "
                "err = str(getattr(res, 'result', '')) if state in ('FAILURE','RETRY','REVOKED') else ''; "
                "print(state); "
                "print(err[:2000] if err else ''); "
                "sys.exit(0 if state == 'SUCCESS' else 1)"
            )
            proc = subprocess.run(
                [sys.executable, "-c", code, payload],
                text=True,
            )
            if proc.returncode == 0:
                _set_local_task_state(task_id, "SUCCESS")
            else:
                _set_local_task_state(task_id, "FAILURE", "Local crawl subprocess failed")
            return

        result = crawl_and_train.apply(
            args=[workspace_id, url, max_pages],
            kwargs={"allow_retry": False},
            task_id=task_id,
            throw=False,
        )
        state = result.state or "UNKNOWN"
        error = str(result.result) if state in {"FAILURE", "RETRY", "REVOKED"} else None
        # For local mode, treat RETRY as terminal failure to avoid hanging in retry state.
        if state == "RETRY":
            state = "FAILURE"
        _set_local_task_state(task_id, state, error)
    except Exception as exc:
        _set_local_task_state(task_id, "FAILURE", str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/overview")
async def get_analytics(
    days: int = 30,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_conversations = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.workspace_id == admin.workspace_id,
            Conversation.created_at >= since,
        )
    )
    total_messages = await db.scalar(
        select(func.count(Message.id)).join(Conversation).where(
            Conversation.workspace_id == admin.workspace_id,
            Message.created_at >= since,
        )
    )
    thumbs_up = await db.scalar(
        select(func.count(MessageFeedback.id)).join(Message).join(Conversation).where(
            Conversation.workspace_id == admin.workspace_id,
            MessageFeedback.feedback_type == FeedbackType.THUMBS_UP,
            MessageFeedback.created_at >= since,
        )
    )
    thumbs_down = await db.scalar(
        select(func.count(MessageFeedback.id)).join(Message).join(Conversation).where(
            Conversation.workspace_id == admin.workspace_id,
            MessageFeedback.feedback_type == FeedbackType.THUMBS_DOWN,
            MessageFeedback.created_at >= since,
        )
    )
    avg_latency = await db.scalar(
        select(func.avg(Message.latency_ms)).join(Conversation).where(
            Conversation.workspace_id == admin.workspace_id,
            Message.latency_ms.isnot(None),
            Message.created_at >= since,
        )
    )

    total_feedback = (thumbs_up or 0) + (thumbs_down or 0)
    satisfaction_rate = round((thumbs_up or 0) / total_feedback * 100, 1) if total_feedback > 0 else None

    # Also return workspace KB status
    ws_result = await db.execute(select(Workspace).where(Workspace.id == admin.workspace_id))
    ws = ws_result.scalar_one_or_none()
    ws_settings = ws.settings if ws and isinstance(ws.settings, dict) else {}

    return {
        "period_days": days,
        "total_conversations": total_conversations or 0,
        "total_messages": total_messages or 0,
        "satisfaction_rate": satisfaction_rate,
        "avg_latency_ms": round(avg_latency or 0),
        "thumbs_up": thumbs_up or 0,
        "thumbs_down": thumbs_down or 0,
        "kb_status": ws_settings.get("kb_status", "not_configured"),
        "kb_trained_url": ws_settings.get("kb_trained_url"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/conversations")
async def admin_list_conversations(
    page: int = 1,
    page_size: int = 50,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Conversation)
        .where(Conversation.workspace_id == admin.workspace_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(min(page_size, 100))
    )
    convs = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "status": c.status,
            "message_count": c.message_count,
            "channel": c.channel,
            "created_at": c.created_at.isoformat(),
        }
        for c in convs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Documents (manual upload — legacy)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str = "",
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ALLOWED_MIME_TYPES = {"application/pdf", "text/plain", "text/markdown"}
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    MAX_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    doc = Document(
        workspace_id=admin.workspace_id,
        title=title or file.filename or "Untitled",
        file_name=file.filename,
        file_size=len(content),
        mime_type=file.content_type,
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    await db.flush()

    from app.workers.tasks import process_document
    process_document.delay(str(doc.id), content.decode("utf-8", errors="ignore"))

    log.info("document.uploaded", doc_id=str(doc.id), title=doc.title)
    return {"id": str(doc.id), "title": doc.title, "status": doc.status}


@router.get("/documents")
async def list_documents(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.workspace_id == admin.workspace_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "file_name": d.file_name,
            "file_size": d.file_size,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == admin.workspace_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# Crawl Pipeline  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 100


@router.post("/crawl")
async def trigger_crawl(
    body: CrawlRequest,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Start the crawl-and-train pipeline for the admin's workspace.

    Queues a Celery task that:
      1. Crawls the given URL
      2. Uploads pages to S3 (workspaces/{workspace_id}/ prefix)
      3. Creates/updates Bedrock KB + Agent (first time only)
      4. Starts ingestion job and waits for completion

    Progress can be polled at GET /api/v1/admin/crawl-status/{task_id}
    or by checking the kb_status in GET /api/v1/admin/analytics/overview.
    """
    url = body.url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    max_pages = max(1, min(body.max_pages, 500))   # clamp to sane range

    # Mark status immediately so the UI can show "crawling" straight away
    ws_result = await db.execute(select(Workspace).where(Workspace.id == admin.workspace_id))
    ws = ws_result.scalar_one_or_none()
    if ws:
        current = dict(ws.settings or {})
        current["kb_status"] = "queued"
        current["kb_trained_url"] = url
        ws.settings = current
        await db.commit()

    workspace_id = str(admin.workspace_id)
    from app.workers.tasks import crawl_and_train

    # In local development, run crawl locally by default so UI progress works even
    # when Docker/Celery workers are misconfigured or disconnected from local DB.
    # Set USE_CELERY_IN_DEV=true only if you intentionally want Celery in dev.
    use_celery_in_dev = os.getenv("USE_CELERY_IN_DEV", "false").lower() in {"1", "true", "yes", "on"}
    use_local_runner = settings.ENVIRONMENT == "development" and not use_celery_in_dev

    # If user explicitly enabled Celery in dev but no worker is reachable, still
    # fall back to local runner rather than leaving task stuck in queued state.
    if settings.ENVIRONMENT == "development" and use_celery_in_dev and not _has_live_celery_worker():
        use_local_runner = True
    if use_local_runner:
        task_id = str(uuid.uuid4())
        _set_local_task_state(task_id, "PENDING")
        Thread(
            target=_run_crawl_locally,
            args=(task_id, workspace_id, url, max_pages),
            daemon=True,
        ).start()
        log.info("crawl.local_runner_started", workspace_id=workspace_id, url=url, task_id=task_id)
        return {
            "task_id": task_id,
            "status": "queued",
            "url": url,
            "max_pages": max_pages,
            "execution": "local_thread",
            "message": "Crawl started locally. Poll /api/v1/admin/crawl-status/{task_id} for progress.",
        }

    try:
        task = crawl_and_train.delay(workspace_id, url, max_pages)
    except Exception as exc:
        if settings.ENVIRONMENT == "development":
            task_id = str(uuid.uuid4())
            _set_local_task_state(task_id, "PENDING")
            Thread(
                target=_run_crawl_locally,
                args=(task_id, workspace_id, url, max_pages),
                daemon=True,
            ).start()
            log.warning(
                "crawl.delay_failed_fallback_local",
                workspace_id=workspace_id,
                url=url,
                task_id=task_id,
                error=str(exc),
            )
            return {
                "task_id": task_id,
                "status": "queued",
                "url": url,
                "max_pages": max_pages,
                "execution": "local_thread",
                "message": "Celery unavailable. Running crawl locally in background.",
            }
        raise

    log.info("crawl.queued", workspace_id=workspace_id, url=url, task_id=task.id)
    return {
        "task_id": task.id,
        "status": "queued",
        "url": url,
        "max_pages": max_pages,
        "message": "Crawl started. Poll /api/v1/admin/crawl-status/{task_id} for progress.",
    }


@router.get("/crawl-status/{task_id}")
async def get_crawl_status(
    task_id: str,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the Celery task state AND the workspace's current kb_status.
    The frontend can poll this every 3-5 seconds after triggering a crawl.

    Response shape:
    {
        "task_id": "...",
        "celery_state": "PENDING" | "STARTED" | "SUCCESS" | "FAILURE",
        "kb_status": "queued" | "crawling" | "uploading" | "provisioning" | "indexing" | "ready" | "failed",
        "kb_error": "...",        # only on failure
        "kb_trained_url": "...",  # the URL that was crawled
        "bedrock_kb_id": "...",   # once provisioned
        "bedrock_agent_id": "...",
    }
    """
    local_task = _get_local_task_state(task_id)
    if local_task:
        celery_state = local_task.get("state") or "UNKNOWN"
        celery_error = local_task.get("error")
    else:
        from celery.result import AsyncResult
        result = AsyncResult(task_id, app=__import__("app.workers.tasks", fromlist=["celery_app"]).celery_app)
        celery_state = result.state
        celery_error = str(result.result) if celery_state in {"FAILURE", "REVOKED"} else None

    # Read current workspace settings for KB status
    ws_result = await db.execute(select(Workspace).where(Workspace.id == admin.workspace_id))
    ws = ws_result.scalar_one_or_none()
    ws_settings = ws.settings if ws and isinstance(ws.settings, dict) else {}

    return {
        "task_id": task_id,
        "celery_state": celery_state,
        "celery_error": celery_error,
        "kb_status": ws_settings.get("kb_status", "unknown"),
        "kb_error": ws_settings.get("kb_error"),
        "kb_trained_url": ws_settings.get("kb_trained_url"),
        "bedrock_kb_id": ws_settings.get("bedrock_kb_id"),
        "bedrock_agent_id": ws_settings.get("bedrock_agent_id"),
        "bedrock_agent_alias_id": ws_settings.get("bedrock_agent_alias_id"),
    }


@router.get("/workspace-settings")
async def get_workspace_settings(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return current workspace Bedrock config for the admin dashboard."""
    ws_result = await db.execute(select(Workspace).where(Workspace.id == admin.workspace_id))
    ws = ws_result.scalar_one_or_none()
    ws_settings = ws.settings if ws and isinstance(ws.settings, dict) else {}
    return {
        "workspace_id": str(admin.workspace_id),
        "workspace_slug": ws.slug if ws else "",
        "kb_status": ws_settings.get("kb_status", "not_configured"),
        "kb_trained_url": ws_settings.get("kb_trained_url"),
        "bedrock_kb_id": ws_settings.get("bedrock_kb_id"),
        "bedrock_agent_id": ws_settings.get("bedrock_agent_id"),
        "has_agent": bool(ws_settings.get("bedrock_agent_id")),
    }
