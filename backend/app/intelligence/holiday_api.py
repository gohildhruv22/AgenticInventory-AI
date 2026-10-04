"""Holiday API (Calendarific) integration with proximity calc and static fallback."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

import httpx
import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger("agenticinventory.intelligence.holiday")

CACHE_TTL = 86400  # 24 hours
CALENDARIFIC_BASE = "https://calendarific.com/api/v2/holidays"

# Static fallback calendar (US major holidays)
STATIC_HOLIDAYS: list[dict] = [
    {"name": "New Year's Day", "month": 1, "day": 1},
    {"name": "Martin Luther King Jr. Day", "month": 1, "day": 20},
    {"name": "Presidents' Day", "month": 2, "day": 17},
    {"name": "Memorial Day", "month": 5, "day": 26},
    {"name": "Independence Day", "month": 7, "day": 4},
    {"name": "Labor Day", "month": 9, "day": 1},
    {"name": "Columbus Day", "month": 10, "day": 13},
    {"name": "Veterans Day", "month": 11, "day": 11},
    {"name": "Thanksgiving", "month": 11, "day": 27},
    {"name": "Christmas Day", "month": 12, "day": 25},
    {"name": "Black Friday", "month": 11, "day": 28},
    {"name": "Cyber Monday", "month": 12, "day": 1},
    {"name": "Valentine's Day", "month": 2, "day": 14},
    {"name": "Mother's Day", "month": 5, "day": 11},
    {"name": "Father's Day", "month": 6, "day": 15},
    {"name": "Halloween", "month": 10, "day": 31},
]


class HolidayAPIService:
    """Fetches upcoming holidays and computes proximity for demand impact."""

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

    async def get_holidays(self, country: str = "US") -> dict:
        """Fetch upcoming holidays and compute proximity.

        Returns:
            dict with ``proximity`` (days to nearest holiday), ``holiday_name``,
            ``is_stale`` flag, and ``fetched_at``.
        """
        today = date.today()
        year = today.year
        cache_key = f"intelligence:holidays:{country.lower()}:{year}"

        cached = await self._get_cached(cache_key)
        if cached:
            # Recompute proximity from cached holidays list
            return self._pick_nearest(cached.get("holidays", []), today)

        settings = get_settings()
        if not settings.CALENDARIFIC_API_KEY:
            logger.info("CALENDARIFIC_API_KEY not set, using static fallback")
            return self._static_fallback(today)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    CALENDARIFIC_BASE,
                    params={
                        "api_key": settings.CALENDARIFIC_API_KEY,
                        "country": country,
                        "year": year,
                        "type": "national",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            holidays_raw = data.get("response", {}).get("holidays", [])
            holidays = []
            for h in holidays_raw:
                d = h.get("date", {}).get("iso", "")
                if d:
                    holidays.append({"name": h["name"], "date": d})

            cache_payload = {"holidays": holidays, "fetched_at": datetime.now(timezone.utc).isoformat()}
            await self._set_cached(cache_key, cache_payload)

            return self._pick_nearest(holidays, today)

        except Exception as exc:
            logger.error("Holiday API fetch failed: %s", exc)
            return self._static_fallback(today)

    def _pick_nearest(self, holidays: list[dict], today: date) -> dict:
        """Find the nearest upcoming holiday from a list."""
        nearest_name = None
        nearest_days = 365

        for h in holidays:
            try:
                h_date = date.fromisoformat(h["date"][:10])
                delta = (h_date - today).days
                if 0 <= delta < nearest_days:
                    nearest_days = delta
                    nearest_name = h["name"]
            except (ValueError, KeyError):
                continue

        return {
            "proximity": nearest_days,
            "holiday_name": nearest_name,
            "is_stale": False,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _static_fallback(self, today: date) -> dict:
        """Use the static holiday calendar as fallback."""
        logger.info("Using static holiday calendar fallback")
        nearest_name = None
        nearest_days = 365

        for h in STATIC_HOLIDAYS:
            try:
                h_date = date(today.year, h["month"], h["day"])
                delta = (h_date - today).days
                if delta < 0:
                    # Try next year
                    h_date = date(today.year + 1, h["month"], h["day"])
                    delta = (h_date - today).days
                if 0 <= delta < nearest_days:
                    nearest_days = delta
                    nearest_name = h["name"]
            except ValueError:
                continue

        return {
            "proximity": nearest_days,
            "holiday_name": nearest_name,
            "is_stale": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
