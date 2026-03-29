"""
app/workers/tasks.py
Celery background tasks — FULLY SYNCHRONOUS.

ROOT CAUSE OF PREVIOUS SILENT FAILURES:
  asyncio.run() inside a Celery prefork worker creates a new event loop
  per call. When multiple asyncio.run() calls exist in the same task
  (e.g. _update_kb_status called from within another asyncio.run()),
  the inner coroutines run on isolated loops whose DB sessions are
  never properly committed. The result: 200 OK from the API endpoint
  (which just queues the task), but nothing actually written to S3 or DB.

THE FIX:
  - All Celery tasks are now 100% synchronous.
  - DB access in workers uses a sync SQLAlchemy session (psycopg2 driver).
  - The crawler is sync (httpx.Client, not AsyncClient).
  - The bedrock_provisioner is sync (boto3, which is already sync).
  - No asyncio anywhere in this file.

Add to requirements.txt:
    psycopg2-binary>=2.9
    httpx>=0.27.0
    beautifulsoup4>=4.12.0
    lxml>=5.0.0
"""
import re
import time
import uuid

import boto3
import structlog
from celery import Celery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.metrics import celery_tasks_total, celery_task_duration_seconds, crawl_jobs_total

log = structlog.get_logger()

celery_app = Celery(
    "tissatech",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_soft_time_limit=600,
    task_time_limit=900,
    worker_max_tasks_per_child=50,
)


# ─────────────────────────────────────────────────────────────────────────────
# Sync DB session factory for workers
# Uses psycopg2 (sync) instead of asyncpg (async-only).
# The DATABASE_URL env var uses asyncpg:// — we swap the driver here.
# ─────────────────────────────────────────────────────────────────────────────

def _make_sync_engine():
    """Convert asyncpg DATABASE_URL to psycopg2 for synchronous worker use."""
    url = settings.DATABASE_URL
    # Replace async driver prefix with sync driver prefix
    sync_url = (
        url
        .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("postgresql+aiopg://", "postgresql+psycopg2://")
    )
    # If it's still a plain postgresql:// URL, leave it (psycopg2 is the default)
    return create_engine(
        sync_url,
        pool_size=2,
        max_overflow=1,
        pool_timeout=30,
        pool_pre_ping=True,    # reconnect if DB connection dropped
    )


_sync_engine = None
_SyncSession = None


def get_sync_session() -> Session:
    """Get a synchronous SQLAlchemy session. Lazily initialises the engine."""
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = _make_sync_engine()
        _SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False)
    return _SyncSession()


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers — fully synchronous
# ─────────────────────────────────────────────────────────────────────────────

def _get_workspace(db: Session, workspace_id: str) -> dict:
    """Fetch workspace row as a plain dict."""
    row = db.execute(
        text("SELECT id, slug, settings FROM workspaces WHERE id = :wid"),
        {"wid": workspace_id},
    ).fetchone()
    if not row:
        raise ValueError(f"Workspace {workspace_id} not found in DB")
    return {
        "id": str(row[0]),
        "slug": row[1],
        "settings": row[2] or {},
    }


def _update_kb_status(workspace_id: str, status: str, error: str = "") -> None:
    """Write kb_status (and optionally kb_error) into workspace.settings JSONB."""
    db = get_sync_session()
    try:
        # Use PostgreSQL JSONB || operator to merge keys
        if error:
            db.execute(
                text("""
                    UPDATE workspaces
                    SET settings = COALESCE(settings, '{}'::jsonb)
                        || jsonb_build_object('kb_status', :status, 'kb_error', :error)
                    WHERE id = :wid
                """),
                {"wid": workspace_id, "status": status, "error": error},
            )
        else:
            db.execute(
                text("""
                    UPDATE workspaces
                    SET settings = COALESCE(settings, '{}'::jsonb)
                        || jsonb_build_object('kb_status', :status)
                        - 'kb_error'
                    WHERE id = :wid
                """),
                {"wid": workspace_id, "status": status},
            )
        db.commit()
        log.info("worker.kb_status_updated", workspace_id=workspace_id, status=status)
    except Exception as exc:
        db.rollback()
        log.error("worker.kb_status_update_failed", error=str(exc))
    finally:
        db.close()


def _save_workspace_settings(workspace_id: str, new_settings: dict) -> None:
    """Overwrite workspace.settings with new_settings dict."""
    import json
    db = get_sync_session()
    try:
        db.execute(
            text("UPDATE workspaces SET settings = :s WHERE id = :wid"),
            {"s": json.dumps(new_settings), "wid": workspace_id},
        )
        db.commit()
        log.info("worker.workspace_settings_saved", workspace_id=workspace_id, keys=list(new_settings.keys()))
    except Exception as exc:
        db.rollback()
        log.error("worker.save_settings_failed", error=str(exc), exc_info=True)
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE: crawl_and_train  (100% synchronous)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_existing_kb_data_source_id(kb_id: str) -> str | None:
    """
    Find a usable data source ID for an existing KB (global fallback mode).
    """
    if not kb_id:
        return None
    try:
        creds = {}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
            creds["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
            creds["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
        bedrock = boto3.client("bedrock-agent", region_name=settings.AWS_REGION, **creds)
        resp = bedrock.list_data_sources(knowledgeBaseId=kb_id, maxResults=100)
        sources = resp.get("dataSourceSummaries", [])
        if not sources:
            return None
        preferred = next(
            (s for s in sources if s.get("status") in {"AVAILABLE", "ACTIVE"}),
            sources[0],
        )
        return preferred.get("dataSourceId")
    except Exception as exc:
        log.warning("worker.resolve_kb_ds_failed", kb_id=kb_id, error=str(exc))
        return None


@celery_app.task(bind=True, max_retries=1, name="crawl_and_train")
def crawl_and_train(
    self,
    workspace_id: str,
    url: str,
    max_pages: int = 100,
    allow_retry: bool = True,
):
    """
    Full knowledge base training pipeline.

    Steps (all synchronous):
      1. Load workspace from DB
      2. Crawl the website (sync httpx)
      3. Upload pages to S3
      4. Provision Bedrock KB + Agent (idempotent)
      5. Start ingestion job
      6. Poll until COMPLETE / FAILED
      7. Update workspace.settings.kb_status

    Progress written to workspace.settings.kb_status at each step so the
    frontend poll endpoint can show live progress.
    """
    task_name = "crawl_and_train"
    task_started_at = time.time()
    task_succeeded = False
    celery_tasks_total.labels(task=task_name, status="started").inc()
    log.info("crawl_and_train.started", workspace_id=workspace_id, url=url)

    try:
        # ── 1. Load workspace ────────────────────────────────────────────────
        db = get_sync_session()
        try:
            workspace = _get_workspace(db, workspace_id)
        finally:
            db.close()

        workspace_slug = workspace["slug"]
        existing_settings = dict(workspace["settings"])
        log.info("crawl_and_train.workspace_loaded", slug=workspace_slug, existing_keys=list(existing_settings.keys()))

        # ── 2. Crawl ──────────────────────────────────────────────────────────
        _update_kb_status(workspace_id, "crawling")

        from app.workers.crawler import crawl_website
        pages = crawl_website(url, max_pages=max_pages)

        if not pages:
            raise RuntimeError(
                f"No pages crawled from {url}. "
                "Check the URL is publicly accessible and returns HTML. "
                "Try opening the URL in a browser to confirm it loads."
            )

        log.info("crawl_and_train.crawl_complete", pages=len(pages), workspace_id=workspace_id)

        # ── 3. Upload to S3 ───────────────────────────────────────────────────
        _update_kb_status(workspace_id, "uploading")

        s3_keys = _upload_pages_to_s3(workspace_id, pages)
        log.info("crawl_and_train.s3_upload_complete", files=len(s3_keys), workspace_id=workspace_id)

        # ── 4. Provision Bedrock (first crawl only) ───────────────────────────
        has_kb = bool(existing_settings.get("bedrock_kb_id"))
        has_agent = bool(existing_settings.get("bedrock_agent_id"))

        # Shared-infra mode (budget friendly):
        # If global Bedrock IDs are configured, map each workspace to the same infra explicitly.
        # This is different from BEDROCK_ALLOW_GLOBAL_FALLBACK and remains safe with retrieval filtering.
        shared_kb_id = (settings.BEDROCK_KNOWLEDGE_BASE_ID or "").strip()
        shared_agent_id = (settings.BEDROCK_AGENT_ID or "").strip()
        shared_alias_id = (settings.BEDROCK_AGENT_ALIAS_ID or "").strip()

        shared_kb_configured = shared_kb_id not in ("", "YOUR_KB_ID")
        shared_agent_configured = shared_agent_id not in ("", "YOUR_AGENT_ID", "test")
        shared_infra_configured = shared_kb_configured and shared_agent_configured

        if (not has_kb or not has_agent) and shared_infra_configured:
            shared_settings: dict[str, str] = {
                "bedrock_kb_id": shared_kb_id,
                "bedrock_agent_id": shared_agent_id,
            }
            if shared_alias_id and shared_alias_id not in ("YOUR_ALIAS_ID", "TSTALIASID"):
                shared_settings["bedrock_agent_alias_id"] = shared_alias_id

            if not existing_settings.get("bedrock_kb_ds_id"):
                shared_ds_id = _resolve_existing_kb_data_source_id(shared_kb_id)
                if shared_ds_id:
                    shared_settings["bedrock_kb_ds_id"] = shared_ds_id

            existing_settings.update(shared_settings)
            _save_workspace_settings(workspace_id, existing_settings)
            has_kb = bool(existing_settings.get("bedrock_kb_id"))
            has_agent = bool(existing_settings.get("bedrock_agent_id"))
            log.info(
                "crawl_and_train.using_shared_bedrock_infra",
                workspace_id=workspace_id,
                kb_id=existing_settings.get("bedrock_kb_id"),
                ds_id=existing_settings.get("bedrock_kb_ds_id"),
                agent_id=existing_settings.get("bedrock_agent_id"),
            )
        elif (not has_kb or not has_agent):
            log.info(
                "crawl_and_train.shared_infra_not_configured",
                workspace_id=workspace_id,
                global_fallback_enabled=settings.BEDROCK_ALLOW_GLOBAL_FALLBACK,
                environment=settings.ENVIRONMENT,
            )

        if not has_kb or not has_agent:
            _update_kb_status(workspace_id, "provisioning")
            log.info("crawl_and_train.provisioning", workspace_id=workspace_id)

            from app.workers.bedrock_provisioner import provision_workspace_bedrock
            provisioned = provision_workspace_bedrock(workspace_id, workspace_slug)

            existing_settings.update(provisioned)
            _save_workspace_settings(workspace_id, existing_settings)
            log.info("crawl_and_train.provisioned", workspace_id=workspace_id, **provisioned)
        else:
            log.info("crawl_and_train.provision_skipped_already_exists", workspace_id=workspace_id)

        # Re-read settings from DB (they were just updated above)
        db = get_sync_session()
        try:
            workspace = _get_workspace(db, workspace_id)
        finally:
            db.close()
        ws_settings = dict(workspace["settings"])

        kb_id = ws_settings["bedrock_kb_id"]
        ds_id = ws_settings["bedrock_kb_ds_id"]

        # ── 5. Start ingestion ────────────────────────────────────────────────
        _update_kb_status(workspace_id, "indexing")

        from app.workers.bedrock_provisioner import start_kb_ingestion, wait_for_ingestion_complete
        job_id = start_kb_ingestion(kb_id, ds_id)

        ws_settings["bedrock_ingestion_job_id"] = job_id
        _save_workspace_settings(workspace_id, ws_settings)

        # ── 6. Poll ingestion ─────────────────────────────────────────────────
        final_status = wait_for_ingestion_complete(kb_id, ds_id, job_id, timeout=600)

        if final_status == "COMPLETE":
            ws_settings["kb_status"] = "ready"
            _save_workspace_settings(workspace_id, ws_settings)
            log.info("crawl_and_train.pipeline_complete", workspace_id=workspace_id, pages=len(pages))
            task_succeeded = True
        else:
            raise RuntimeError(f"Bedrock ingestion job ended with status: {final_status}")

    except Exception as exc:
        crawl_jobs_total.labels(status="failed").inc()
        celery_tasks_total.labels(task=task_name, status="failed").inc()
        log.error("crawl_and_train.pipeline_failed", workspace_id=workspace_id, error=str(exc), exc_info=True)
        _update_kb_status(workspace_id, "failed", error=str(exc)[:500])
        if allow_retry:
            # max_retries=1 so this retries once after 2 minutes, then gives up
            raise self.retry(exc=exc, countdown=120, max_retries=1)
        raise
    finally:
        if task_succeeded:
            celery_tasks_total.labels(task=task_name, status="success").inc()
        celery_task_duration_seconds.labels(task=task_name).observe(
            max(time.time() - task_started_at, 0.0)
        )


# ─────────────────────────────────────────────────────────────────────────────
# S3 upload helper
# ─────────────────────────────────────────────────────────────────────────────

def _upload_pages_to_s3(workspace_id: str, pages) -> list[str]:
    """
    Upload each crawled page as a .txt file to S3.
    Key: workspaces/{workspace_id}/{url_slug}.txt
    Content: "Source: {url}\nTitle: {title}\n\n{text}"
    Returns list of S3 keys uploaded.
    """
    if not settings.S3_KNOWLEDGE_BASE_BUCKET:
        raise RuntimeError(
            "S3_KNOWLEDGE_BASE_BUCKET is not set in .env. "
            "Cannot upload crawled pages."
        )

    creds = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
        creds["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        creds["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

    s3 = boto3.client("s3", region_name=settings.AWS_REGION, **creds)
    bucket = settings.S3_KNOWLEDGE_BASE_BUCKET
    prefix = f"workspaces/{workspace_id}/"
    keys = []

    for i, page in enumerate(pages):
        # Build filename from URL — safe for S3 keys
        slug = re.sub(r"https?://", "", page.url)
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
        slug = slug[:100]
        key = f"{prefix}{i:04d}_{slug}.txt"

        content = f"Source: {page.url}\nTitle: {page.title}\n\n{page.text}"

        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
                Metadata={
                    "workspace-id": workspace_id,
                    "source-url": page.url[:500],
                },
            )
            keys.append(key)
            log.debug("s3.uploaded", key=key, bytes=len(content))
        except Exception as exc:
            # Log but continue — partial upload is better than total failure
            log.error("s3.upload_failed", key=key, error=str(exc))

    if not keys:
        raise RuntimeError(
            f"S3 upload failed for all {len(pages)} pages. "
            "Check AWS credentials and S3_KNOWLEDGE_BASE_BUCKET permission."
        )

    log.info("s3.upload_complete", bucket=bucket, prefix=prefix, files=len(keys))
    return keys


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY: process_document (pgvector — also made sync)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str, content: str):
    """
    Legacy document upload → pgvector embeddings.
    NOTE: This also uses synchronous DB access now.
    """
    try:
        _process_document_sync(document_id, content)
    except Exception as exc:
        log.error("task.process_document_failed", doc_id=document_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


def _process_document_sync(document_id: str, content: str):
    import json

    chunks = _chunk_text(content, chunk_size=1500, overlap=200)

    creds = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
        creds["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        creds["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

    bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION, **creds)

    db = get_sync_session()
    try:
        # Mark as processing
        db.execute(
            text("UPDATE documents SET status = 'processing' WHERE id = :did"),
            {"did": document_id},
        )
        db.commit()

        # Generate embeddings and insert chunks
        for i, chunk_text in enumerate(chunks):
            resp = bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v1",
                body=json.dumps({"inputText": chunk_text[:8000]}).encode(),
                contentType="application/json",
                accept="application/json",
            )
            embedding = json.loads(resp["body"].read())["embedding"]
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

            db.execute(
                text("""
                    INSERT INTO document_chunks
                        (id, document_id, chunk_index, content, embedding, token_count, metadata)
                    VALUES
                        (gen_random_uuid(), :doc_id, :idx, :content, :emb::vector, :tokens, '{}'::jsonb)
                """),
                {
                    "doc_id": document_id,
                    "idx": i,
                    "content": chunk_text,
                    "emb": embedding_str,
                    "tokens": len(chunk_text.split()),
                },
            )

        db.execute(
            text("UPDATE documents SET status = 'indexed', chunk_count = :n WHERE id = :did"),
            {"n": len(chunks), "did": document_id},
        )
        db.commit()
        log.info("document.indexed", doc_id=document_id, chunks=len(chunks))
    except Exception:
        db.rollback()
        db.execute(
            text("UPDATE documents SET status = 'failed' WHERE id = :did"),
            {"did": document_id},
        )
        db.commit()
        raise
    finally:
        db.close()


def _chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# PERIODIC: cleanup
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task
def cleanup_expired_sessions():
    """Remove expired sessions and refresh tokens (sync)."""
    db = get_sync_session()
    try:
        db.execute(text("DELETE FROM sessions WHERE expires_at < NOW()"))
        db.execute(text("DELETE FROM refresh_tokens WHERE expires_at < NOW()"))
        db.commit()
        log.info("cleanup.completed")
    except Exception as exc:
        db.rollback()
        log.error("cleanup.failed", error=str(exc))
    finally:
        db.close()
