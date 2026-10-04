"""Async SMTP client with aiosmtplib, TLS support, and retry logic."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import uuid4

import aiosmtplib

logger = logging.getLogger("agenticinventory.email.smtp")

# Retry backoff schedule in seconds
RETRY_DELAYS = [30, 120, 480]
MAX_RETRIES = 3


@dataclass
class EmailMessage:
    """Structured email message ready to send."""

    to: str
    subject: str
    body_text: str
    body_html: str = ""
    from_email: str = ""
    from_name: str = "AgenticInventory AI"
    reply_to: str = ""
    message_id: str = field(default_factory=lambda: f"<{uuid4()}@agenticinventory.ai>")


@dataclass
class SendResult:
    """Result of an email send attempt."""

    success: bool
    message_id: str
    error: str = ""
    attempts: int = 1
    sent_at: datetime | None = None


class SMTPClient:
    """Async SMTP client wrapping aiosmtplib with TLS and retry support."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        from_email: str = "",
        from_name: str = "AgenticInventory AI",
        timeout: int = 30,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_email = from_email
        self._from_name = from_name
        self._timeout = timeout
        logger.info("SMTPClient initialized: host=%s port=%d tls=%s", host, port, use_tls)

    def _build_mime(self, msg: EmailMessage) -> MIMEMultipart:
        """Build a MIME message from an EmailMessage."""
        mime = MIMEMultipart("alternative")
        mime["From"] = f"{msg.from_name or self._from_name} <{msg.from_email or self._from_email}>"
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        mime["Message-ID"] = msg.message_id

        if msg.reply_to:
            mime["Reply-To"] = msg.reply_to

        # Attach plain-text part first
        mime.attach(MIMEText(msg.body_text, "plain", "utf-8"))

        # Attach HTML part (preferred)
        if msg.body_html:
            mime.attach(MIMEText(msg.body_html, "html", "utf-8"))

        return mime

    async def send(self, msg: EmailMessage) -> SendResult:
        """Send an email with retry logic.

        Retries up to MAX_RETRIES times with exponential backoff.
        """
        msg.from_email = msg.from_email or self._from_email
        msg.from_name = msg.from_name or self._from_name

        mime = self._build_mime(msg)
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Sending email attempt %d/%d: to=%s subject=%s",
                    attempt,
                    MAX_RETRIES,
                    msg.to,
                    msg.subject[:50],
                )

                await aiosmtplib.send(
                    mime,
                    hostname=self._host,
                    port=self._port,
                    username=self._username if self._username else None,
                    password=self._password if self._password else None,
                    start_tls=self._use_tls,
                    timeout=self._timeout,
                )

                logger.info(
                    "Email sent successfully: to=%s message_id=%s",
                    msg.to,
                    msg.message_id,
                )

                return SendResult(
                    success=True,
                    message_id=msg.message_id,
                    attempts=attempt,
                    sent_at=datetime.now(timezone.utc),
                )

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Email send attempt %d failed: %s",
                    attempt,
                    last_error,
                )

                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAYS[attempt - 1]
                    logger.info("Retrying in %d seconds...", delay)
                    await asyncio.sleep(delay)

        logger.error(
            "Email send failed after %d attempts: to=%s error=%s",
            MAX_RETRIES,
            msg.to,
            last_error,
        )

        return SendResult(
            success=False,
            message_id=msg.message_id,
            error=last_error,
            attempts=MAX_RETRIES,
        )

    async def test_connection(self) -> bool:
        """Test SMTP connectivity without sending."""
        try:
            # Disable auto-TLS so we control STARTTLS explicitly based on _use_tls.
            # (aiosmtplib auto-negotiates STARTTLS on port 587 by default, which then
            # makes an explicit starttls() call raise "Connection already using TLS".)
            smtp = aiosmtplib.SMTP(
                hostname=self._host,
                port=self._port,
                timeout=self._timeout,
                use_tls=False,
                start_tls=False,
            )
            await smtp.connect()
            if self._use_tls:
                await smtp.starttls()
            if self._username and self._password:
                await smtp.login(self._username, self._password)
            await smtp.quit()
            logger.info("SMTP connection test successful")
            return True
        except Exception as exc:
            logger.error("SMTP connection test failed: %s", exc)
            return False
