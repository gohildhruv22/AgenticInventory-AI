"""News API integration service with httpx, sentiment extraction, and Redis caching."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger("agenticinventory.intelligence.news")

CACHE_TTL = 1800  # 30 minutes
NEWS_API_BASE = "https://newsapi.org/v2/everything"


class NewsAPIService:
    """Fetches supply-chain-relevant news and extracts sentiment."""

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

    async def get_news(self, keyword: str, category: str | None = None) -> dict:
        """Fetch news articles relevant to a product keyword.

        Returns:
            dict with ``sentiment`` (-1.0 to 1.0), ``headlines`` (top 3),
            ``article_count``, ``is_stale`` flag, and ``fetched_at``.
        """
        search_term = f"{keyword} supply chain" if category else keyword
        cache_key = f"intelligence:news:{search_term.lower().strip()}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        settings = get_settings()
        if not settings.NEWS_API_KEY:
            logger.info("NEWS_API_KEY not set, using fallback for '%s'", keyword)
            return self._fallback(keyword)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    NEWS_API_BASE,
                    params={
                        "q": search_term,
                        "language": "en",
                        "sortBy": "relevancy",
                        "pageSize": 10,
                        "apiKey": settings.NEWS_API_KEY,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            articles = data.get("articles", [])
            headlines = [a["title"] for a in articles[:3] if a.get("title")]
            sentiment = self._compute_sentiment(articles)

            result = {
                "sentiment": sentiment,
                "headlines": headlines,
                "article_count": len(articles),
                "is_stale": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._set_cached(cache_key, result)
            return result

        except Exception as exc:
            logger.error("News API fetch failed for '%s': %s", keyword, exc)
            return self._fallback(keyword)

    def _compute_sentiment(self, articles: list[dict]) -> float:
        """Simple keyword-based sentiment scoring.

        Positive keywords push toward +1.0, negative toward -1.0.
        Returns a float in [-1.0, 1.0].
        """
        positive = {"growth", "surge", "increase", "strong", "boost", "record", "gain", "rise", "profit", "expand"}
        negative = {"shortage", "decline", "disruption", "crisis", "delay", "tariff", "recall", "drop", "loss", "risk"}

        score = 0.0
        total = 0

        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            for word in positive:
                if word in text:
                    score += 1.0
                    total += 1
            for word in negative:
                if word in text:
                    score -= 1.0
                    total += 1

        if total == 0:
            return 0.0
        return max(-1.0, min(1.0, score / total))

    def _fallback(self, keyword: str) -> dict:
        logger.info("Using fallback data for News API '%s'", keyword)
        return {
            "sentiment": 0.0,
            "headlines": [],
            "article_count": 0,
            "is_stale": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
