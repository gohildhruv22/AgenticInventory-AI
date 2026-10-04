"""Runtime control for the supplier-reply ingestor background loop.

Separated from `eta_ingestor.py` so that tests can import the pure
`run_ingestor_cycle` function without touching module-level loop state.
"""
from __future__ import annotations

import asyncio
import logging

from app.services.eta_ingestor import run_ingestor_cycle

logger = logging.getLogger("agenticinventory.services.eta_ingestor_runtime")


_loop_task: asyncio.Task | None = None
_loop_active: bool = False


async def _loop(interval_seconds: int) -> None:
    global _loop_active

    logger.info("EtaIngestor loop running (interval=%ds)", interval_seconds)
    while _loop_active:
        try:
            await run_ingestor_cycle()
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            logger.exception("EtaIngestor cycle raised: %s", exc)

        for _ in range(interval_seconds):
            if not _loop_active:
                break
            await asyncio.sleep(1)
    logger.info("EtaIngestor loop stopped")


def start_eta_ingestor(*, interval_seconds: int = 60) -> None:
    """Start the ingestor background task. Idempotent."""
    global _loop_task, _loop_active

    if _loop_active and _loop_task is not None and not _loop_task.done():
        logger.warning("start_eta_ingestor: already running")
        return

    _loop_active = True
    _loop_task = asyncio.create_task(_loop(interval_seconds), name="eta_ingestor_loop")


async def stop_eta_ingestor() -> None:
    """Signal the loop to exit and await its cancellation."""
    global _loop_task, _loop_active

    _loop_active = False
    if _loop_task is not None and not _loop_task.done():
        _loop_task.cancel()
        try:
            await _loop_task
        except (asyncio.CancelledError, Exception):
            pass
    _loop_task = None


def is_eta_ingestor_active() -> bool:
    return (
        _loop_active and _loop_task is not None and not _loop_task.done()
    )
