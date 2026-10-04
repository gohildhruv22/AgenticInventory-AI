import uuid
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Time, Text, func
from app.models._types import JSONType, UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmailConfiguration(Base):
    __tablename__ = "email_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), nullable=False, unique=True)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str] = mapped_column(String(100), nullable=False, default="AgenticInventory AI")
    supplier_mappings: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=75.00)
    daily_report_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_report_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(0, 0))
    daily_report_recipients: Mapped[dict] = mapped_column(JSONType, nullable=False, default=list)
    admin_notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Feature 004: optional IMAP host/port for the ETA agent ingestor.
    # SMTP username/password are reused; if either column is NULL the ingestor is
    # disabled for this configuration.
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Confidence threshold at or above which an EtaExtraction is auto-applied
    # to the delivery without going through the review queue (data-model §6).
    eta_auto_apply_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("80.00"), server_default="80.00"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
