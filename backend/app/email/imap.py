"""Async IMAP client wrapper for the Supplier Delivery ETA Agent ingestor.

Thin, opinionated layer over ``aioimaplib`` that:
  - exposes a clean async context manager (``connect`` / ``close``);
  - yields parsed messages as ``RawMessage`` dataclass instances via
    :meth:`ImapClient.fetch_unseen`;
  - lets the ingestor mark messages as seen only after they have been
    successfully persisted (research.md §1 / §4);
  - retries each network call up to 3 times with linear backoff per
    constitution IX ("Resilient by Default").

A protocol-equivalent in-memory fake lives in
``app/email/_imap_fake.py`` and is the only implementation used in tests.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol

import aioimaplib
import mailparser  # mail-parser package

logger = logging.getLogger("agenticinventory.email.imap")

_DEFAULT_ATTEMPTS = 3
_DEFAULT_BASE_DELAY = 0.5  # seconds


@dataclass(frozen=True)
class RawMessage:
    """A single fetched message, already parsed into headers + body."""

    uid: str
    message_id: str | None
    from_address: str
    subject: str
    date: str | None
    body_text: str
    headers: dict[str, str] = field(default_factory=dict)


class ImapClientProtocol(Protocol):
    """Surface used by the ingestor — kept minimal so the fake matches it."""

    async def connect(self, host: str, port: int, user: str, password: str) -> None: ...
    async def close(self) -> None: ...
    def fetch_unseen(self, mailbox: str = "INBOX") -> AsyncIterator[RawMessage]: ...
    async def mark_seen(self, uid: str) -> None: ...


async def _with_retries(
    op_name: str,
    coro_factory,
    *,
    attempts: int = _DEFAULT_ATTEMPTS,
    base_delay: float = _DEFAULT_BASE_DELAY,
):
    """Run ``coro_factory()`` up to ``attempts`` times with linear backoff."""
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await coro_factory()
        except Exception as exc:  # noqa: BLE001 — boundary retry
            last_exc = exc
            logger.warning(
                "IMAP %s attempt %d/%d failed: %s",
                op_name,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    assert last_exc is not None  # for type-checker
    raise last_exc


class ImapClient:
    """Real IMAP client used in production. Wraps ``aioimaplib.IMAP4_SSL``."""

    def __init__(self) -> None:
        self._imap: aioimaplib.IMAP4_SSL | None = None

    async def connect(self, host: str, port: int, user: str, password: str) -> None:
        async def _go():
            client = aioimaplib.IMAP4_SSL(host=host, port=port, timeout=30)
            await client.wait_hello_from_server()
            login_resp = await client.login(user, password)
            if login_resp.result != "OK":
                raise RuntimeError(f"IMAP login failed: {login_resp.result}")
            self._imap = client
            logger.info("IMAP connected: host=%s port=%s user=%s", host, port, user)

        await _with_retries("connect", _go)

    async def close(self) -> None:
        if self._imap is None:
            return
        try:
            await self._imap.logout()
        except Exception:  # pragma: no cover — best-effort shutdown
            pass
        self._imap = None

    async def fetch_unseen(
        self, mailbox: str = "INBOX"
    ) -> AsyncIterator[RawMessage]:
        if self._imap is None:
            raise RuntimeError("ImapClient.fetch_unseen called before connect()")
        client = self._imap

        async def _select():
            return await client.select(mailbox)

        await _with_retries("select", _select)

        async def _search():
            return await client.search("UNSEEN")

        search_resp = await _with_retries("search", _search)
        if search_resp.result != "OK" or not search_resp.lines:
            return
        # `search_resp.lines[0]` is bytes like b"1 2 3" (or b"").
        line0 = search_resp.lines[0]
        if isinstance(line0, (bytes, bytearray)):
            uid_part = line0.decode("ascii", errors="ignore").strip()
        else:
            uid_part = str(line0).strip()
        if not uid_part:
            return
        for uid in uid_part.split():
            async def _fetch():
                return await client.fetch(uid, "(BODY.PEEK[])")

            fetch_resp = await _with_retries(f"fetch[{uid}]", _fetch)
            if fetch_resp.result != "OK" or len(fetch_resp.lines) < 2:
                logger.warning("IMAP fetch of uid=%s returned no data", uid)
                continue
            raw_bytes = fetch_resp.lines[1]
            if not isinstance(raw_bytes, (bytes, bytearray)):
                raw_bytes = str(raw_bytes).encode("utf-8", errors="ignore")
            yield _parse_raw(uid, bytes(raw_bytes))

    async def mark_seen(self, uid: str) -> None:
        if self._imap is None:
            raise RuntimeError("ImapClient.mark_seen called before connect()")
        client = self._imap

        async def _go():
            return await client.store(uid, "+FLAGS", "\\Seen")

        await _with_retries(f"mark_seen[{uid}]", _go)


def _parse_raw(uid: str, raw: bytes) -> RawMessage:
    """Parse a raw RFC-5322 byte string into a ``RawMessage``."""
    parsed = mailparser.parse_from_bytes(raw)
    headers = {k: str(v) for k, v in (parsed.headers or {}).items()}

    from_field = ""
    if parsed.from_:
        first = parsed.from_[0]
        if isinstance(first, tuple) and len(first) >= 2:
            from_field = str(first[1] or first[0] or "").lower()
        else:
            from_field = str(first).lower()

    body_text = parsed.text_plain[0] if parsed.text_plain else (parsed.body or "")
    return RawMessage(
        uid=str(uid.decode() if isinstance(uid, (bytes, bytearray)) else uid),
        message_id=parsed.message_id or headers.get("Message-Id") or headers.get("Message-ID"),
        from_address=from_field,
        subject=str(parsed.subject or headers.get("Subject", "")),
        date=str(parsed.date) if parsed.date else headers.get("Date"),
        body_text=str(body_text or ""),
        headers=headers,
    )


@asynccontextmanager
async def open_imap_client(
    host: str, port: int, user: str, password: str
) -> AsyncIterator[ImapClient]:
    """Async context manager — guarantees `close()` even on exceptions."""
    client = ImapClient()
    try:
        await client.connect(host, port, user, password)
        yield client
    finally:
        await client.close()
