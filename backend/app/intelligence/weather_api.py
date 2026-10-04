"""OpenWeatherMap integration service with disruption risk scoring and Redis caching."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger("agenticinventory.intelligence.weather")

CACHE_TTL = 3600  # 60 minutes
WEATHER_API_BASE = "https://api.openweathermap.org/data/2.5/weather"


class WeatherAPIService:
    """Fetches weather data and scores supply-chain disruption risk."""

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

    async def get_weather(self, location: str | None = None) -> dict:
        """Fetch weather data and compute disruption risk.

        Args:
            location: City,Country code (e.g. "New York,US"). Falls back to config default.

        Returns:
            dict with ``impact`` (0-100 disruption risk), ``summary`` (human-readable),
            ``is_stale`` flag, and ``fetched_at``.
        """
        settings = get_settings()
        loc = location or settings.INTELLIGENCE_DEFAULT_LOCATION
        cache_key = f"intelligence:weather:{loc.lower().strip()}"

        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if not settings.OPENWEATHER_API_KEY:
            logger.info("OPENWEATHER_API_KEY not set, using fallback")
            return self._fallback()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    WEATHER_API_BASE,
                    params={
                        "q": loc,
                        "appid": settings.OPENWEATHER_API_KEY,
                        "units": "metric",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            impact = self._compute_disruption_risk(data)
            summary = self._build_summary(data)

            result = {
                "impact": impact,
                "summary": summary,
                "is_stale": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._set_cached(cache_key, result)
            return result

        except Exception as exc:
            logger.error("Weather API fetch failed for '%s': %s", loc, exc)
            return self._fallback()

    def _compute_disruption_risk(self, data: dict) -> float:
        """Score supply-chain disruption risk from weather conditions (0-100)."""
        risk = 0.0
        weather_conditions = data.get("weather", [{}])
        main_weather = weather_conditions[0].get("main", "").lower() if weather_conditions else ""
        wind_speed = data.get("wind", {}).get("speed", 0)

        # Severe weather conditions
        severe = {"thunderstorm": 70, "tornado": 95, "hurricane": 95, "snow": 50, "blizzard": 80}
        moderate = {"rain": 20, "drizzle": 10, "fog": 15, "mist": 10, "haze": 5}

        for condition, score in severe.items():
            if condition in main_weather:
                risk = max(risk, score)
        for condition, score in moderate.items():
            if condition in main_weather:
                risk = max(risk, score)

        # High wind adds risk
        if wind_speed > 20:
            risk = min(100, risk + 30)
        elif wind_speed > 10:
            risk = min(100, risk + 10)

        return round(risk, 1)

    def _build_summary(self, data: dict) -> str:
        weather_desc = data.get("weather", [{}])[0].get("description", "unknown") if data.get("weather") else "unknown"
        temp = data.get("main", {}).get("temp", "N/A")
        wind = data.get("wind", {}).get("speed", 0)
        return f"{weather_desc}, {temp}°C, wind {wind} m/s"

    def _fallback(self) -> dict:
        logger.info("Using fallback weather data")
        return {
            "impact": 0.0,
            "summary": "Weather data unavailable",
            "is_stale": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
