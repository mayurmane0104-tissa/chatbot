"""
app/api/health.py
Health check endpoints for load balancers and monitoring systems.
"""
import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

router = APIRouter()
START_TIME = time.time()


@router.get("/health")
async def health():
    return {"status": "ok", "uptime_seconds": int(time.time() - START_TIME)}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Deep health: checks DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


@router.get("/health/live")
async def liveness():
    """Shallow health for container orchestration."""
    return {"status": "alive"}
