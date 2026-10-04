"""Pytest fixtures shared across the backend test tree.

Forces the test process onto an in-memory SQLite database and registers
the helpers required by feature 004 ETA agent tests:

  - ``test_session`` — fresh `AsyncSession` against an isolated in-memory
    SQLite engine, all tables created.
  - ``stub_eta_agent`` — patches `OpenAIChatCompletionClient.create` so
    :class:`DeliveryEtaAgent.extract` returns whatever JSON the test
    enqueues (no network calls).
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from dataclasses import dataclass
from typing import Any, AsyncIterator

import pytest

# Force SQLite + an isolated file before any `app.*` import. Using a
# file-backed DB (not :memory:) lets multiple connections (sync + async)
# see the same schema.
_TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_eta.db")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB_PATH}")
os.environ.setdefault("AUTONOMOUS_LOOP_ENABLED", "false")
os.environ.setdefault("ETA_INGESTOR_ENABLED", "false")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


# Drop any pre-existing test DB at session start.
def _reset_db_file() -> None:
    try:
        if os.path.exists(_TEST_DB_PATH):
            os.remove(_TEST_DB_PATH)
    except OSError:
        pass


_reset_db_file()


@pytest.fixture(scope="session", autouse=True)
def _init_schema() -> None:
    """Create all tables once per test session."""
    from app.database import Base, engine
    from app import models  # noqa: F401 — register tables

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


@pytest.fixture
async def test_session() -> AsyncIterator[Any]:
    """Fresh `AsyncSession` per test; cleans feature-004 tables on entry
    so cross-test commits don't bleed into the next test.
    """
    from sqlalchemy import text
    from app.database import async_session_factory

    # Tables to truncate per-test. Order matters for FKs.
    _CLEAN_TABLES = (
        "delivery_timeline_entries",
        "eta_review_items",
        "action_logs",
        "supplier_replies",
        "deliveries",
        "supplier_orders",
        "email_configurations",
    )

    async with async_session_factory() as session:
        for tbl in _CLEAN_TABLES:
            try:
                await session.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                # Table may not exist in some test profiles — ignore.
                pass
        await session.commit()
        try:
            yield session
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# DeliveryEtaAgent stub
# ---------------------------------------------------------------------------


@dataclass
class _StubResponse:
    content: str


class _StubModelClient:
    """Replaces the real `OpenAIChatCompletionClient` for unit tests.

    The test enqueues a list of JSON-encoded responses via
    :meth:`set_responses`; each call to :meth:`create` pops the next one.
    """

    def __init__(self) -> None:
        self._queue: deque[str] = deque()

    def set_responses(self, responses: list[str | dict]) -> None:
        self._queue.clear()
        for r in responses:
            self._queue.append(r if isinstance(r, str) else json.dumps(r))

    async def create(self, messages: list, **_kwargs: Any) -> _StubResponse:
        if not self._queue:
            raise RuntimeError("StubModelClient: no queued responses")
        return _StubResponse(content=self._queue.popleft())

    async def close(self) -> None:
        return None


@pytest.fixture
def stub_model_client(monkeypatch: pytest.MonkeyPatch) -> _StubModelClient:
    """Patch `create_base_agent_config` so the agent uses the stub client."""
    from app.agents import delivery_eta as de_mod

    stub = _StubModelClient()
    original = de_mod.create_base_agent_config

    def _patched(name: str, system_message: str, tier: str) -> dict:
        cfg = original(name=name, system_message=system_message, tier=tier)
        cfg["model_client"] = stub
        return cfg

    monkeypatch.setattr(de_mod, "create_base_agent_config", _patched)
    return stub
