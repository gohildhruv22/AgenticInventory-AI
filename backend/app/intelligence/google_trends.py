"""Google Trends integration service with async execution and Redis caching."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from pytrends.request import TrendReq

from app.config import get_settings

logger = logging.getLogger("agenticinventory.intelligence.trends")

CACHE_TTL = 1800  # 30 minutes


class GoogleTrendsService:
    """Fetches Google Trends interest data for product keywords."""

    def __init__(self, redis_client: aioredis.Redis | None = None):
        self._redis = redis_client

    async def _get_cached(self, key: str) -> dict | None:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(key)
            if raw:
                logger.debug("Cache hit: %s", key)
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis cache read failed: %s", exc)
        return None

    async def _set_cached(self, key: str, value: dict, ttl: int = CACHE_TTL) -> None:
        if not self._redis:
            return
        try:
            await self._redis.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("Redis cache write failed: %s", exc)

    async def get_trends(self, keyword: str) -> dict:
        """Fetch Google Trends interest score and direction for a keyword.

        Returns:
            dict with ``score`` (0-100), ``direction`` ('rising'|'stable'|'declining'),
            ``is_stale`` flag, and ``fetched_at`` timestamp.
        """
        cache_key = f"intelligence:trends:{keyword.lower().strip()}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        try:
            result = await asyncio.to_thread(self._fetch_sync, keyword)
            await self._set_cached(cache_key, result)
            return result
        except Exception as exc:
            logger.error("Google Trends fetch failed for '%s': %s", keyword, exc)
            # Try returning stale cached data
            stale = await self._get_stale(cache_key)
            if stale:
                stale["is_stale"] = True
                return stale
            return self._fallback(keyword)

    def _fetch_sync(self, keyword: str) -> dict:
        """Synchronous pytrends call, executed in a thread."""
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload([keyword], cat=0, timeframe="now 7-d")
        df = pytrends.interest_over_time()

        if df.empty or keyword not in df.columns:
            return self._fallback(keyword)

        values = df[keyword].tolist()
        current = values[-1] if values else 50
        avg_first_half = sum(values[: len(values) // 2]) / max(len(values) // 2, 1)
        avg_second_half = sum(values[len(values) // 2 :]) / max(len(values) // 2, 1)

        if avg_second_half > avg_first_half * 1.15:
            direction = "rising"
        elif avg_second_half < avg_first_half * 0.85:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "score": float(current),
            "direction": direction,
            "is_stale": False,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _get_stale(self, key: str) -> dict | None:
        """Try to get any previously cached value even if expired."""
        # Redis deletes expired keys, so we use a separate backup key
        return await self._get_cached(f"{key}:backup")

    def _fallback(self, keyword: str) -> dict:
        logger.info("Using fallback data for Google Trends '%s'", keyword)
        return {
            "score": 50.0,
            "direction": "stable",
            "is_stale": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
