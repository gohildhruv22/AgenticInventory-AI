import asyncio
import logging

import redis.asyncio as redis
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session_factory

router = APIRouter(tags=["health"])
logger = logging.getLogger("agenticinventory")


@router.get("/health")
async def health_check():
    settings = get_settings()
    checks = {}

    # Database
    try:
        async with async_session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=3)
        checks["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = "unhealthy"

    # Redis
    try:
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await asyncio.wait_for(r.ping(), timeout=3)
        await r.aclose()
        checks["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = "unhealthy"

    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {"status": overall, "checks": checks}
