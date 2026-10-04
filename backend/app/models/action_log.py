import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from app.models._types import JSONType, UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), nullable=False, index=True)
    before_state: Mapped[dict] = mapped_column(JSONType, nullable=False)
    after_state: Mapped[dict] = mapped_column(JSONType, nullable=False)
    compensating_action: Mapped[dict] = mapped_column(JSONType, nullable=False)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType(as_uuid=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="executed")
    reasoning_trace: Mapped[dict] = mapped_column(JSONType, nullable=False)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
