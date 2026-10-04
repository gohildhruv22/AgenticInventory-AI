"""Monitoring API endpoints — control the autonomous monitoring loop and trigger manual cycles."""

from fastapi import APIRouter, BackgroundTasks

from app.services.monitoring_service import (
    is_monitoring_active,
    run_monitoring_cycle,
    start_monitoring,
    stop_monitoring,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.post("/start")
async def start_monitoring_loop(
    interval: int = 60,
):
    """Start the autonomous monitoring loop.

    Args:
        interval: Seconds between monitoring cycles (default 60).
    """
    if is_monitoring_active():
        return {"status": "already_running", "message": "Monitoring loop is already active"}

    start_monitoring(interval_seconds=interval)
    return {
        "status": "started",
        "interval_seconds": interval,
        "message": "Autonomous monitoring loop started",
    }


@router.post("/stop")
async def stop_monitoring_loop():
    """Stop the autonomous monitoring loop."""
    if not is_monitoring_active():
        return {"status": "not_running", "message": "Monitoring loop is not active"}

    stop_monitoring()
    return {"status": "stopped", "message": "Monitoring loop stopped"}


@router.get("/status")
async def monitoring_status():
    """Get the current monitoring loop status."""
    return {
        "active": is_monitoring_active(),
    }


@router.post("/trigger")
async def trigger_monitoring_cycle(background_tasks: BackgroundTasks):
    """Trigger a single monitoring cycle manually via BackgroundTasks.

    This runs the monitoring cycle in the background and returns immediately.
    Results are broadcast via WebSocket.
    """
    background_tasks.add_task(run_monitoring_cycle)
    return {
        "status": "triggered",
        "message": "Monitoring cycle queued — results will be broadcast via WebSocket",
    }


@router.post("/trigger/sync")
async def trigger_monitoring_cycle_sync():
    """Trigger a single monitoring cycle synchronously and return results.

    Useful for testing and debugging — waits for the cycle to complete.
    """
    result = await run_monitoring_cycle()
    return {"status": "completed", "result": result}
