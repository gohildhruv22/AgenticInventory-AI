"""eta_agent_init — Supplier Delivery ETA Agent schema.

Feature 004 — see specs/004-supplier-delivery-eta-agent/data-model.md §6.

This migration:
  1. Creates `supplier_replies`, `delivery_timeline_entries`, `eta_review_items`
     with all indexes (data-model §1–§3).
  2. Adds `deliveries.has_pending_review` (Boolean NOT NULL DEFAULT false, indexed).
  3. Adds `email_configurations.imap_host`, `imap_port`,
     `eta_auto_apply_threshold` (data-model §6).
  4. Backfills `delivery_timeline_entries` from the legacy
     `deliveries.stage_history` JSON column with `actor_type='simulator'`. The
     original column is left in place (read-only) for one release as a safety
     net.

The migration is idempotent against the SQLite dev DB where the parent
`deliveries` / `email_configurations` tables were originally created via
``Base.metadata.create_all()``; existing columns are tested with the inspector
before ALTER statements run.

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260521_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.eta_agent_init")


# Map legacy stage_history.stage strings to the new timeline event_type enum.
# Anything not in this mapping falls back to "note" with the legacy stage
# captured in DeliveryTimelineEntry.note.
_LEGACY_STAGE_TO_EVENT: dict[str, str] = {
    "ordered": "acknowledged",
    "pending": "acknowledged",
    "confirmed": "eta_confirmed",
    "in_transit": "acknowledged",
    "shipped": "acknowledged",
    "out_for_delivery": "acknowledged",
    "at_risk": "at_risk",
    "delivered": "delivered",
}


def _has_column(inspector: sa.engine.reflection.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_table(inspector: sa.engine.reflection.Inspector, table: str) -> bool:
    return inspector.has_table(table)


def _to_iso(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            # Accept both "...Z" and "...+00:00".
            cleaned = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------ tables
    if not _has_table(inspector, "supplier_replies"):
        op.create_table(
            "supplier_replies",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("message_id", sa.String(512), nullable=False, unique=True),
            sa.Column("from_address", sa.String(255), nullable=False, index=True),
            sa.Column("subject", sa.String(998), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("body_excerpt", sa.Text, nullable=False),
            sa.Column("raw_headers", sa.Text, nullable=False, server_default="{}"),
            sa.Column(
                "matched_order_id",
                sa.CHAR(36),
                sa.ForeignKey("supplier_orders.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "matched_delivery_id",
                sa.CHAR(36),
                sa.ForeignKey("deliveries.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "processing_status",
                sa.String(20),
                nullable=False,
                server_default="new",
            ),
            sa.Column("agent_response", sa.Text, nullable=True),
            sa.Column("error_detail", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_supplier_replies_received_at",
            "supplier_replies",
            ["received_at"],
        )
        op.create_index(
            "ix_supplier_replies_status_created",
            "supplier_replies",
            ["processing_status", "created_at"],
        )
        op.create_index(
            "ix_supplier_replies_matched_delivery",
            "supplier_replies",
            ["matched_delivery_id"],
        )

    if not _has_table(inspector, "eta_review_items"):
        op.create_table(
            "eta_review_items",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column(
                "supplier_reply_id",
                sa.CHAR(36),
                sa.ForeignKey("supplier_replies.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "candidate_delivery_id",
                sa.CHAR(36),
                sa.ForeignKey("deliveries.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "candidate_order_ids",
                sa.Text,
                nullable=False,
                server_default="[]",
            ),
            sa.Column("agent_intent", sa.String(20), nullable=False),
            sa.Column("agent_parsed_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("agent_confidence", sa.Numeric(5, 2), nullable=False),
            sa.Column("agent_reasoning", sa.Text, nullable=False),
            sa.Column("raised_reason", sa.String(40), nullable=False),
            sa.Column(
                "resolution_state",
                sa.String(15),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("resolved_by", sa.String(128), nullable=True),
            sa.Column("resolution_payload", sa.Text, nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "raised_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_eta_review_state_raised",
            "eta_review_items",
            ["resolution_state", "raised_at"],
        )
        op.create_index(
            "ix_eta_review_candidate_delivery",
            "eta_review_items",
            ["candidate_delivery_id"],
        )

    if not _has_table(inspector, "delivery_timeline_entries"):
        op.create_table(
            "delivery_timeline_entries",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column(
                "delivery_id",
                sa.CHAR(36),
                sa.ForeignKey("deliveries.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(30), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor_type", sa.String(10), nullable=False),
            sa.Column("actor_id", sa.String(128), nullable=True),
            sa.Column("parsed_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
            sa.Column("supplier_excerpt", sa.Text, nullable=True),
            sa.Column(
                "source_reply_id",
                sa.CHAR(36),
                sa.ForeignKey("supplier_replies.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "source_review_id",
                sa.CHAR(36),
                sa.ForeignKey("eta_review_items.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_delivery_timeline_delivery_id",
            "delivery_timeline_entries",
            ["delivery_id"],
        )
        op.create_index(
            "ix_delivery_timeline_occurred_at",
            "delivery_timeline_entries",
            ["occurred_at"],
        )
        op.create_index(
            "ix_delivery_timeline_delivery_occurred",
            "delivery_timeline_entries",
            ["delivery_id", "occurred_at"],
        )
        op.create_index(
            "ix_delivery_timeline_source_reply",
            "delivery_timeline_entries",
            ["source_reply_id"],
        )

    # ------------------------------------------------------- ALTER deliveries
    inspector = sa.inspect(bind)
    if _has_table(inspector, "deliveries") and not _has_column(
        inspector, "deliveries", "has_pending_review"
    ):
        with op.batch_alter_table("deliveries") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "has_pending_review",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )
        op.create_index(
            "ix_deliveries_has_pending_review",
            "deliveries",
            ["has_pending_review"],
        )

    # ----------------------------------------- ALTER email_configurations
    inspector = sa.inspect(bind)
    if _has_table(inspector, "email_configurations"):
        with op.batch_alter_table("email_configurations") as batch_op:
            if not _has_column(inspector, "email_configurations", "imap_host"):
                batch_op.add_column(
                    sa.Column("imap_host", sa.String(255), nullable=True)
                )
            if not _has_column(inspector, "email_configurations", "imap_port"):
                batch_op.add_column(
                    sa.Column("imap_port", sa.Integer(), nullable=True)
                )
            if not _has_column(
                inspector, "email_configurations", "eta_auto_apply_threshold"
            ):
                batch_op.add_column(
                    sa.Column(
                        "eta_auto_apply_threshold",
                        sa.Numeric(5, 2),
                        nullable=False,
                        server_default="80.00",
                    )
                )

    # ------------------------------------------------------ backfill timeline
    _backfill_timeline_from_stage_history(bind)


def _backfill_timeline_from_stage_history(bind: sa.engine.Connection) -> None:
    """Copy legacy `deliveries.stage_history` entries into
    `delivery_timeline_entries` with `actor_type='simulator'`. Idempotent — if
    a timeline row already exists for the (delivery_id, occurred_at,
    event_type) triple it is skipped.
    """
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "deliveries") or not _has_table(
        inspector, "delivery_timeline_entries"
    ):
        return

    deliveries_rows = bind.execute(
        sa.text("SELECT id, stage_history FROM deliveries")
    ).fetchall()
    if not deliveries_rows:
        return

    # Existing keys to make the backfill idempotent.
    existing = bind.execute(
        sa.text(
            "SELECT delivery_id, event_type, occurred_at "
            "FROM delivery_timeline_entries"
        )
    ).fetchall()
    existing_keys: set[tuple[str, str, str]] = {
        (str(r[0]), str(r[1]), str(r[2])) for r in existing
    }

    insert_stmt = sa.text(
        """
        INSERT INTO delivery_timeline_entries
            (id, delivery_id, event_type, occurred_at, actor_type,
             actor_id, parsed_date, confidence, supplier_excerpt,
             source_reply_id, source_review_id, note, created_at)
        VALUES
            (:id, :delivery_id, :event_type, :occurred_at, :actor_type,
             :actor_id, :parsed_date, :confidence, :supplier_excerpt,
             :source_reply_id, :source_review_id, :note, :created_at)
        """
    )

    backfilled = 0
    for delivery_id, stage_history in deliveries_rows:
        if stage_history is None:
            continue
        if isinstance(stage_history, str):
            try:
                entries = json.loads(stage_history)
            except (TypeError, ValueError):
                continue
        else:
            entries = stage_history
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            legacy_stage = str(
                entry.get("stage")
                or entry.get("status")
                or entry.get("event")
                or "note"
            )
            occurred_at = _to_iso(
                entry.get("timestamp")
                or entry.get("occurred_at")
                or entry.get("at")
                or entry.get("created_at")
            )
            if occurred_at is None:
                continue
            event_type = _LEGACY_STAGE_TO_EVENT.get(legacy_stage, "note")
            note = (
                None
                if event_type != "note"
                else f"legacy stage_history: {legacy_stage}"
            )
            key = (str(delivery_id), event_type, occurred_at.isoformat())
            if key in existing_keys:
                continue
            bind.execute(
                insert_stmt,
                {
                    "id": str(uuid.uuid4()),
                    "delivery_id": str(delivery_id),
                    "event_type": event_type,
                    "occurred_at": occurred_at,
                    "actor_type": "simulator",
                    "actor_id": None,
                    "parsed_date": None,
                    "confidence": None,
                    "supplier_excerpt": None,
                    "source_reply_id": None,
                    "source_review_id": None,
                    "note": note,
                    "created_at": occurred_at,
                },
            )
            existing_keys.add(key)
            backfilled += 1

    logger.info(
        "eta_agent_init: backfilled %d delivery_timeline_entries from stage_history",
        backfilled,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "email_configurations"):
        with op.batch_alter_table("email_configurations") as batch_op:
            if _has_column(inspector, "email_configurations", "eta_auto_apply_threshold"):
                batch_op.drop_column("eta_auto_apply_threshold")
            if _has_column(inspector, "email_configurations", "imap_port"):
                batch_op.drop_column("imap_port")
            if _has_column(inspector, "email_configurations", "imap_host"):
                batch_op.drop_column("imap_host")

    if _has_table(inspector, "deliveries") and _has_column(
        inspector, "deliveries", "has_pending_review"
    ):
        try:
            op.drop_index("ix_deliveries_has_pending_review", table_name="deliveries")
        except Exception:  # pragma: no cover — index may not exist
            pass
        with op.batch_alter_table("deliveries") as batch_op:
            batch_op.drop_column("has_pending_review")

    for tbl in (
        "delivery_timeline_entries",
        "eta_review_items",
        "supplier_replies",
    ):
        if _has_table(inspector, tbl):
            op.drop_table(tbl)
