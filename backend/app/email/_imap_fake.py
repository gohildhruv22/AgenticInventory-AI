"""In-memory IMAP fake used by every test that exercises the ingestor.

Protocol-equivalent to :class:`app.email.imap.ImapClient` — same public
methods, same return shapes. No network, no parsing of raw bytes; tests
construct :class:`RawMessage` instances directly.

Usage::

    fake = FakeImapClient([
        RawMessage(uid="1", message_id="<a@x>", ...),
        RawMessage(uid="2", message_id="<b@x>", ...),
    ])
    await fake.connect("imap.example", 993, "u", "p")
    async for msg in fake.fetch_unseen():
        ...
    await fake.mark_seen("1")
    await fake.close()
"""
from __future__ import annotations

from typing import AsyncIterator

from app.email.imap import RawMessage


class FakeImapClient:
    def __init__(self, messages: list[RawMessage] | None = None) -> None:
        self._messages: list[RawMessage] = list(messages or [])
        self._seen: set[str] = set()
        self._connected: bool = False
        # Test hooks — flip to True to exercise the retry/error paths.
        self.connect_should_fail: bool = False
        self.fetch_should_fail: bool = False
        self.mark_seen_should_fail: bool = False
        # Audit trail used by tests.
        self.connect_calls: list[tuple[str, int, str, str]] = []
        self.mark_seen_calls: list[str] = []

    # -- protocol -------------------------------------------------------------

    async def connect(self, host: str, port: int, user: str, password: str) -> None:
        self.connect_calls.append((host, port, user, password))
        if self.connect_should_fail:
            raise RuntimeError("FakeImapClient: forced connect failure")
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def fetch_unseen(self, mailbox: str = "INBOX") -> AsyncIterator[RawMessage]:
        if not self._connected:
            raise RuntimeError("FakeImapClient.fetch_unseen called before connect()")
        if self.fetch_should_fail:
            raise RuntimeError("FakeImapClient: forced fetch failure")
        for msg in list(self._messages):
            if msg.uid in self._seen:
                continue
            yield msg

    async def mark_seen(self, uid: str) -> None:
        if not self._connected:
            raise RuntimeError("FakeImapClient.mark_seen called before connect()")
        if self.mark_seen_should_fail:
            raise RuntimeError("FakeImapClient: forced mark_seen failure")
        self.mark_seen_calls.append(uid)
        self._seen.add(uid)

    # -- test helpers ---------------------------------------------------------

    def push(self, message: RawMessage) -> None:
        """Append a message after construction (e.g. between ingestor cycles)."""
        self._messages.append(message)

    def reset_seen(self) -> None:
        """Clear the seen-set so the same fixture replays."""
        self._seen.clear()
