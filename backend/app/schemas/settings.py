from datetime import datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class EmailConfigCreate(BaseModel):
    # All SMTP credentials are optional at the schema level. The /settings/email
    # PUT endpoint falls back to env-level defaults for any missing field on
    # first-time setup so the UI can save partial configurations gracefully.
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(default="", max_length=255)
    smtp_password: str | None = Field(default=None)
    smtp_use_tls: bool = True
    from_email: str = Field(default="", max_length=255)
    from_name: str = Field(default="AgenticInventory AI", max_length=100)
    supplier_mappings: dict[str, Any] = {}
    confidence_threshold: Decimal = Field(default=Decimal("75.00"), ge=0, le=100)
    daily_report_enabled: bool = True
    daily_report_time: time = time(0, 0)
    daily_report_recipients: list[str] = []
    admin_notification_email: EmailStr | None = None
    # Feature 004 — Supplier ETA Agent (T055).
    imap_host: str | None = Field(default=None, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    eta_auto_apply_threshold: Decimal = Field(
        default=Decimal("80.00"), ge=0, le=100
    )


class EmailConfigUpdate(BaseModel):
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    from_email: EmailStr | None = None
    from_name: str | None = Field(default=None, max_length=100)
    supplier_mappings: dict[str, Any] | None = None
    confidence_threshold: Decimal | None = Field(default=None, ge=0, le=100)
    daily_report_enabled: bool | None = None
    daily_report_time: time | None = None
    daily_report_recipients: list[str] | None = None
    admin_notification_email: EmailStr | None = None
    imap_host: str | None = Field(default=None, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    eta_auto_apply_threshold: Decimal | None = Field(default=None, ge=0, le=100)


class EmailConfigResponse(BaseModel):
    id: UUID
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_tls: bool
    from_email: str
    from_name: str
    supplier_mappings: dict[str, Any]
    confidence_threshold: Decimal
    daily_report_enabled: bool
    daily_report_time: time
    daily_report_recipients: list[str]
    admin_notification_email: str | None
    imap_host: str | None = None
    imap_port: int | None = None
    eta_auto_apply_threshold: Decimal = Decimal("80.00")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
