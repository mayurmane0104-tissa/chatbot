"""
app/api/debug_crawl.py
Temporary debug endpoint — lets you test the crawl pipeline SYNCHRONOUSLY
without going through Celery. Hit this endpoint directly to verify:
  1. The crawler can reach your URL
  2. S3 upload works
  3. AWS credentials are correct

REMOVE THIS FILE IN PRODUCTION.
Add to main.py:
  from app.api import debug_crawl
  app.include_router(debug_crawl.router, prefix="/api/v1/debug", tags=["debug"])
"""
import re
import boto3
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_admin
from app.core.config import settings

router = APIRouter()


class CrawlTestRequest(BaseModel):
    url: str
    max_pages: int = 3       # keep small for a quick test


@router.post("/test-crawl")
async def test_crawl_sync(body: CrawlTestRequest, admin=Depends(require_admin)):
    """
    Synchronously crawl up to max_pages pages and return the results.
    Does NOT upload to S3 or touch Bedrock — just tests the crawler.
    """
    from app.workers.crawler import crawl_website
    try:
        pages = crawl_website(body.url, max_pages=body.max_pages)
        return {
            "ok": True,
            "pages_found": len(pages),
            "pages": [
                {
                    "url": p.url,
                    "title": p.title,
                    "chars": p.char_count,
                    "preview": p.text[:300],
                }
                for p in pages
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/test-s3-upload")
async def test_s3_upload(admin=Depends(require_admin)):
    """
    Upload a tiny test file to S3 to verify credentials and bucket access.
    """
    creds = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_ACCESS_KEY_ID.get_secret_value():
        creds["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        creds["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

    bucket = settings.S3_KNOWLEDGE_BASE_BUCKET
    key = f"workspaces/{admin.workspace_id}/test-upload.txt"

    if not bucket:
        return {"ok": False, "error": "S3_KNOWLEDGE_BASE_BUCKET not set in .env"}

    try:
        s3 = boto3.client("s3", region_name=settings.AWS_REGION, **creds)
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=b"TissaTech S3 upload test - OK",
            ContentType="text/plain",
        )
        return {
            "ok": True,
            "bucket": bucket,
            "key": key,
            "message": f"Successfully uploaded to s3://{bucket}/{key}",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "bucket": bucket}


@router.get("/test-celery-task")
async def test_celery_task(url: str, admin=Depends(require_admin)):
    """
    Queue a real crawl_and_train task and return its task ID.
    Monitor progress via GET /api/v1/admin/crawl-status/{task_id}
    """
    from app.workers.tasks import crawl_and_train
    task = crawl_and_train.delay(str(admin.workspace_id), url, 5)
    return {
        "task_id": task.id,
        "status": "queued",
        "poll_url": f"/api/v1/admin/crawl-status/{task.id}",
    }


@router.get("/workspace-settings")
async def debug_workspace_settings(admin=Depends(require_admin)):
    """Show current workspace.settings so you can see what Bedrock IDs are stored."""
    from sqlalchemy import text
    from app.db.session import get_db
    from fastapi import Depends
    import json

    # Direct DB read
    from app.workers.tasks import get_sync_session
    db = get_sync_session()
    try:
        row = db.execute(
            text("SELECT id, slug, settings FROM workspaces WHERE id = :wid"),
            {"wid": str(admin.workspace_id)},
        ).fetchone()
        return {
            "workspace_id": str(row[0]),
            "slug": row[1],
            "settings": row[2] or {},
            "s3_bucket_configured": bool(settings.S3_KNOWLEDGE_BASE_BUCKET),
            "s3_bucket": settings.S3_KNOWLEDGE_BASE_BUCKET or "(not set)",
            "bedrock_role_configured": bool(settings.BEDROCK_AGENT_ROLE_ARN),
        }
    finally:
        db.close()
