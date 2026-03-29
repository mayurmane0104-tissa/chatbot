"""
app/api/debug.py
Debug endpoints — ONLY available in development mode.
Use these to verify your AWS/Bedrock config is working.
"""
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/debug/config")
async def check_config():
    """Shows which env vars are set (values masked for security)."""
    if settings.is_production:
        return {"error": "Debug endpoints disabled in production"}

    def mask(val: str) -> str:
        if not val or val in ("", "YOUR_AGENT_ID", "YOUR_KB_ID", "test"):
            return "NOT SET"
        return val[:4] + "..." + val[-4:] if len(val) > 8 else "SET"

    return {
        "environment": settings.ENVIRONMENT,
        "aws_region": settings.AWS_REGION,
        "aws_key_id": mask(settings.AWS_ACCESS_KEY_ID.get_secret_value() if settings.AWS_ACCESS_KEY_ID else ""),
        "bedrock_agent_id": mask(settings.BEDROCK_AGENT_ID),
        "bedrock_alias_id": mask(settings.BEDROCK_AGENT_ALIAS_ID),
        "bedrock_model_id": settings.BEDROCK_MODEL_ID,
        "bedrock_kb_id": mask(settings.BEDROCK_KNOWLEDGE_BASE_ID),
        "database_url_set": bool(settings.DATABASE_URL),
        "redis_url": settings.REDIS_URL[:20] + "...",
        "agent_configured": bool(
            settings.BEDROCK_AGENT_ID and
            settings.BEDROCK_AGENT_ID not in ("", "YOUR_AGENT_ID", "test")
        ),
    }


@router.get("/debug/bedrock-test")
async def test_bedrock():
    """Sends a test message to Bedrock and returns the full response."""
    if settings.is_production:
        return {"error": "Debug endpoints disabled in production"}

    from app.agents.bedrock_client import bedrock_client
    chunks = []
    error = None

    try:
        async for chunk in bedrock_client.invoke_agent_streaming(
            user_message="Say hello in exactly 5 words.",
            session_id="debug-test-session",
            allow_global_fallback=True,
        ):
            chunks.append(chunk)
    except Exception as e:
        error = str(e)

    text_chunks = [c for c in chunks if c.get("type") == "text"]
    end_chunks = [c for c in chunks if c.get("type") == "end"]
    error_chunks = [c for c in chunks if c.get("type") == "error"]

    return {
        "success": len(text_chunks) > 0,
        "response": "".join(c.get("content", "") for c in text_chunks),
        "metadata": end_chunks[0].get("metadata") if end_chunks else None,
        "error": error_chunks[0].get("content") if error_chunks else error,
        "raw_chunks": chunks,
    }


@router.get("/debug/db-test")
async def test_db():
    """Tests database connectivity and lists all tables."""
    if settings.is_production:
        return {"error": "Debug endpoints disabled in production"}

    from sqlalchemy import text
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
            ))
            tables = [row[0] for row in result.fetchall()]
        return {"connected": True, "tables": tables, "table_count": len(tables)}
    except Exception as e:
        return {"connected": False, "error": str(e)}
