import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import CorrelationIdMiddleware, setup_logging
from app.websocket.manager import ws_manager

settings = get_settings()
logger = logging.getLogger("agenticinventory")


def create_app() -> FastAPI:
    setup_logging(debug=settings.DEBUG)

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)

    # Routers
    from app.api.health import router as health_router
    from app.api.auth import router as auth_router
    from app.api.inventory import router as inventory_router
    from app.api.agents import router as agents_router
    from app.api.deliveries import router as deliveries_router
    from app.api.reports import router as reports_router
    from app.api.settings import router as settings_router
    from app.api.monitoring import router as monitoring_router
    from app.api.orders import router as orders_router
    from app.api.pipeline import router as pipeline_router
    from app.api.eta_reviews import router as eta_reviews_router

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(deliveries_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(monitoring_router, prefix="/api/v1")
    app.include_router(orders_router, prefix="/api/v1")
    app.include_router(pipeline_router, prefix="/api/v1")
    app.include_router(eta_reviews_router, prefix="/api/v1")

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                event = data.get("event", "")
                if event == "subscribe:room":
                    room = data.get("data", {}).get("room", "general")
                    await ws_manager.join_room(websocket, room)
                elif event == "unsubscribe:room":
                    room = data.get("data", {}).get("room", "general")
                    await ws_manager.leave_room(websocket, room)
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    # Seed endpoint
    from app.api.seed import router as seed_router
    app.include_router(seed_router, prefix="/api/v1")

    # Startup hook — auto-create tables (safe for SQLite + Postgres dev)
    @app.on_event("startup")
    async def startup_event():
        from app.database import init_db, auto_seed_demo_data, auto_seed_demo_activity
        try:
            await init_db()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.warning(f"init_db failed (may already exist): {e}")

        try:
            inserted = await auto_seed_demo_data()
            if inserted:
                logger.info(f"Auto-seeded {inserted} demo inventory items")
        except Exception as e:
            logger.warning(f"auto_seed_demo_data failed: {e}")

        try:
            activity = await auto_seed_demo_activity()
            if any(activity.values()):
                logger.info(
                    "Auto-seeded demo activity: "
                    f"{activity['decisions']} decisions, "
                    f"{activity['forecasts']} forecasts, "
                    f"{activity['orders']} orders, "
                    f"{activity['deliveries']} deliveries, "
                    f"{activity['reports']} reports"
                )
        except Exception as e:
            logger.warning(f"auto_seed_demo_activity failed: {e}")

        # Autonomous agent pipeline — runs continuously without user interaction
        if settings.AUTONOMOUS_LOOP_ENABLED:
            try:
                from app.services.monitoring_service import start_monitoring
                start_monitoring(interval_seconds=settings.AUTONOMOUS_LOOP_INTERVAL_SECONDS)
                logger.info(
                    "Autonomous agent pipeline started (interval=%ds, auto_order=%s)",
                    settings.AUTONOMOUS_LOOP_INTERVAL_SECONDS,
                    settings.AUTONOMOUS_AUTO_ORDER_ENABLED,
                )
            except Exception as e:
                logger.error(f"Failed to start autonomous pipeline: {e}", exc_info=True)
        else:
            logger.info("Autonomous agent pipeline disabled by config")



    # Shutdown hook — stop monitoring loop on app exit
    @app.on_event("shutdown")
    async def shutdown_event():
        from app.services.monitoring_service import stop_monitoring
        stop_monitoring()
        logger.info("Monitoring loop stopped on shutdown")

    logger.info(f"{settings.APP_NAME} started")

    return app


app = create_app()
