"""Intelligence aggregator — queries all 4 APIs concurrently and merges results."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.config import get_settings
from app.intelligence.google_trends import GoogleTrendsService
from app.intelligence.holiday_api import HolidayAPIService
from app.intelligence.news_api import NewsAPIService
from app.intelligence.weather_api import WeatherAPIService

logger = logging.getLogger("agenticinventory.intelligence.aggregator")


@dataclass
class IntelligenceSignals:
    """Unified intelligence payload for the Demand Forecast Agent."""

    trends_score: float = 50.0
    trend_direction: str = "stable"
    news_sentiment: float = 0.0
    news_headlines: list[str] = field(default_factory=list)
    weather_impact: float = 0.0
    weather_summary: str = "Weather data unavailable"
    holiday_proximity: int = 365
    holiday_name: str | None = None
    staleness_flags: list[str] = field(default_factory=list)
    fetched_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class IntelligenceAggregator:
    """Queries all 4 intelligence APIs concurrently and merges into a unified payload."""

    def __init__(self, redis_client: aioredis.Redis | None = None):
        self._redis = redis_client
        self._trends = GoogleTrendsService(redis_client)
        self._news = NewsAPIService(redis_client)
        self._weather = WeatherAPIService(redis_client)
        self._holidays = HolidayAPIService(redis_client)

    async def gather_signals(
        self,
        keyword: str,
        category: str | None = None,
        location: str | None = None,
    ) -> IntelligenceSignals:
        """Fetch all intelligence signals concurrently.

        Args:
            keyword: Product name or search term.
            category: Product category for news filtering.
            location: Location for weather lookup.

        Returns:
            Merged ``IntelligenceSignals`` with partial-failure handling.
        """
        logger.info("Gathering intelligence signals for '%s'", keyword)

        results = await asyncio.gather(
            self._trends.get_trends(keyword),
            self._news.get_news(keyword, category),
            self._weather.get_weather(location),
            self._holidays.get_holidays(),
            return_exceptions=True,
        )

        trends_data = self._safe_result(results[0], "trends")
        news_data = self._safe_result(results[1], "news")
        weather_data = self._safe_result(results[2], "weather")
        holiday_data = self._safe_result(results[3], "holidays")

        staleness_flags: list[str] = []
        if trends_data.get("is_stale"):
            staleness_flags.append("google_trends")
        if news_data.get("is_stale"):
            staleness_flags.append("news_api")
        if weather_data.get("is_stale"):
            staleness_flags.append("weather_api")
        if holiday_data.get("is_stale"):
            staleness_flags.append("holiday_api")

        signals = IntelligenceSignals(
            trends_score=trends_data.get("score", 50.0),
            trend_direction=trends_data.get("direction", "stable"),
            news_sentiment=news_data.get("sentiment", 0.0),
            news_headlines=news_data.get("headlines", []),
            weather_impact=weather_data.get("impact", 0.0),
            weather_summary=weather_data.get("summary", "Weather data unavailable"),
            holiday_proximity=holiday_data.get("proximity", 365),
            holiday_name=holiday_data.get("holiday_name"),
            staleness_flags=staleness_flags,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "Intelligence gathered: trends=%.1f(%s) news=%.2f weather=%.1f holiday=%dd stale=%s",
            signals.trends_score,
            signals.trend_direction,
            signals.news_sentiment,
            signals.weather_impact,
            signals.holiday_proximity,
            staleness_flags or "none",
        )
        return signals

    def _safe_result(self, result: dict | BaseException, source: str) -> dict:
        """Handle exceptions from asyncio.gather(return_exceptions=True)."""
        if isinstance(result, BaseException):
            logger.error("Intelligence source '%s' failed: %s", source, result)
            return {"is_stale": True}
        return result


async def get_redis_client() -> aioredis.Redis | None:
    """Create a Redis client, returning None if unavailable."""
    settings = get_settings()
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable, caching disabled: %s", exc)
        return None
