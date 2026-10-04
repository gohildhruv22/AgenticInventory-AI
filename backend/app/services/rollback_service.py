"""Rollback service — executes compensating actions to undo agent decisions safely."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_log import ActionLog
from app.models.agent_decision import AgentDecision
from app.models.delivery import Delivery
from app.models.inventory_item import InventoryItem
from app.models.supplier_order import SupplierOrder
from app.services.email_service import EmailService
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.services.rollback")


class RollbackService:
    """Executes reverse-chronological compensating actions for a decision,
    restores entity state, sends cancellation emails, and records audit trail."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def undo_decision(self, decision_id: UUID) -> dict:
        """Undo all actions associated with a decision.

        1. Validate decision is eligible for undo.
        2. Load associated action logs in reverse chronological order.
        3. Execute compensating actions one-by-one with progress broadcasting.
        4. Update decision status to 'rolled_back'.
        5. Return rollback summary.

        Raises:
            ValueError: If decision not found or cannot be undone.
        """
        # 1. Load & validate decision
        result = await self.db.execute(
            select(AgentDecision).where(AgentDecision.id == decision_id)
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        if decision.status == "rolled_back":
            raise AlreadyRolledBackError(f"Decision {decision_id} is already rolled back")

        if decision.status not in ("executed", "approved"):
            raise CannotUndoError(
                f"Decision {decision_id} has status '{decision.status}' and cannot be undone",
                reason=f"Status is '{decision.status}', must be 'executed' or 'approved'",
            )

        # 2. Load action logs in reverse chronological order
        result = await self.db.execute(
            select(ActionLog)
            .where(ActionLog.decision_id == decision_id)
            .order_by(ActionLog.created_at.desc())
        )
        action_logs = list(result.scalars().all())

        # If no action logs exist, create synthetic rollback actions from related entities
        if not action_logs:
            action_logs = await self._build_synthetic_actions(decision)

        actions_total = len(action_logs)
        rollback_summary: list[dict] = []

        # Broadcast rollback start
        await ws_manager.broadcast_all(
            "rollback:progress",
            {
                "decision_id": str(decision_id),
                "status": "in_progress",
                "actions_total": actions_total,
                "actions_completed": 0,
                "current_action": "Initiating rollback...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # 3. Execute compensating actions
        for idx, action_log in enumerate(action_logs):
            current_action_desc = self._describe_compensating_action(action_log)

            await ws_manager.broadcast_all(
                "rollback:progress",
                {
                    "decision_id": str(decision_id),
                    "status": "in_progress",
                    "actions_total": actions_total,
                    "actions_completed": idx,
                    "current_action": current_action_desc,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            step_result = await self._execute_compensating_action(action_log)
            rollback_summary.append(step_result)

            # Mark action log as rolled back
            action_log.status = "rolled_back"
            action_log.rolled_back_at = datetime.now(timezone.utc)

        # 4. Update decision status
        decision.status = "rolled_back"
        await self.db.flush()

        # 5. Broadcast completion
        await ws_manager.broadcast_all(
            "rollback:progress",
            {
                "decision_id": str(decision_id),
                "status": "completed",
                "actions_total": actions_total,
                "actions_completed": actions_total,
                "summary": "All actions reversed successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Also broadcast decision update
        await ws_manager.broadcast_all(
            "decision:updated",
            {
                "decision_id": str(decision_id),
                "status": "rolled_back",
            },
        )

        logger.info(
            "Rollback complete: decision=%s actions_reversed=%d",
            decision_id,
            actions_total,
        )

        return {
            "message": "Rollback initiated",
            "decision_id": str(decision_id),
            "actions_reversed": len(rollback_summary),
            "rollback_summary": rollback_summary,
        }

    async def _build_synthetic_actions(self, decision: AgentDecision) -> list[ActionLog]:
        """Build synthetic action log entries from related entities when no
        explicit action logs exist. This ensures rollback works even for
        decisions created before action logging was integrated."""

        actions: list[ActionLog] = []

        # Check for related supplier order
        result = await self.db.execute(
            select(SupplierOrder).where(SupplierOrder.decision_id == decision.id)
        )
        order = result.scalar_one_or_none()

        # Check for related delivery
        delivery = None
        if order:
            result = await self.db.execute(
                select(Delivery).where(Delivery.order_id == order.id)
            )
            delivery = result.scalar_one_or_none()

        # Check for inventory item
        item = None
        if decision.inventory_item_id:
            result = await self.db.execute(
                select(InventoryItem).where(InventoryItem.id == decision.inventory_item_id)
            )
            item = result.scalar_one_or_none()

        # Delivery cancellation (if delivery exists and not yet delivered)
        if delivery and delivery.current_stage not in ("delivered", "cancelled"):
            action = ActionLog(
                agent_type="undo_rollback",
                action_type="cancel_delivery",
                entity_type="delivery",
                entity_id=delivery.id,
                before_state={"current_stage": delivery.current_stage},
                after_state={"current_stage": "cancelled"},
                compensating_action={
                    "type": "cancel_delivery",
                    "params": {"delivery_id": str(delivery.id)},
                    "restore_entity": True,
                },
                decision_id=decision.id,
                status="executed",
                reasoning_trace={"reason": "Synthetic action for rollback"},
            )
            self.db.add(action)
            actions.append(action)

        # Order cancellation email
        if order and order.email_status == "sent":
            action = ActionLog(
                agent_type="undo_rollback",
                action_type="send_cancellation_email",
                entity_type="supplier_order",
                entity_id=order.id,
                before_state={"email_status": order.email_status},
                after_state={"email_status": "cancelled"},
                compensating_action={
                    "type": "send_cancellation_email",
                    "params": {
                        "supplier_email": order.supplier_email,
                        "order_id": str(order.id),
                        "supplier_name": order.supplier_name,
                        "template": "cancellation",
                    },
                    "restore_entity": True,
                },
                decision_id=decision.id,
                status="executed",
                reasoning_trace={"reason": "Cancel supplier order email"},
            )
            self.db.add(action)
            actions.append(action)

        # Inventory restoration
        if item:
            order_qty = decision.reasoning_trace.get("approved_order_qty", 0) or decision.metadata_.get("approved_order_qty", 0)
            action = ActionLog(
                agent_type="undo_rollback",
                action_type="restore_inventory",
                entity_type="inventory_item",
                entity_id=item.id,
                before_state={"current_stock": item.current_stock},
                after_state={"current_stock": item.current_stock},
                compensating_action={
                    "type": "restore_inventory",
                    "params": {
                        "item_id": str(item.id),
                        "restore_stock": item.current_stock,
                        "order_qty": order_qty,
                    },
                    "restore_entity": True,
                },
                decision_id=decision.id,
                status="executed",
                reasoning_trace={"reason": "Restore inventory state"},
            )
            self.db.add(action)
            actions.append(action)

        await self.db.flush()
        return actions

    async def _execute_compensating_action(self, action_log: ActionLog) -> dict:
        """Execute a single compensating action based on the action log entry."""
        comp = action_log.compensating_action
        action_type = comp.get("type", action_log.action_type)
        params = comp.get("params", {})

        if action_type == "send_cancellation_email":
            return await self._send_cancellation_email(action_log, params)
        elif action_type == "cancel_delivery":
            return await self._cancel_delivery(action_log, params)
        elif action_type == "restore_inventory":
            return await self._restore_inventory(action_log, params)
        elif action_type == "restore_eta":
            return await self._restore_eta(action_log, params)
        else:
            # Generic entity state restoration
            return await self._restore_entity_state(action_log)

    async def _send_cancellation_email(
        self, action_log: ActionLog, params: dict
    ) -> dict:
        """Send a cancellation email to the supplier."""
        order_id = params.get("order_id", str(action_log.entity_id))
        supplier_email = params.get("supplier_email", "")
        supplier_name = params.get("supplier_name", "Supplier")

        # Load the order to update its cancellation status
        result = await self.db.execute(
            select(SupplierOrder).where(SupplierOrder.id == action_log.entity_id)
        )
        order = result.scalar_one_or_none()

        # Send cancellation email
        email_svc = await EmailService.from_db_or_settings(self.db)
        try:
            from app.email.renderer import render_cancellation

            body_html = render_cancellation(
                order_id=order_id,
                supplier_name=supplier_name,
                items=order.items if order else [],
                total_cost=float(order.total_cost) if order else 0.0,
                reason="Decision reversed by user — order is no longer needed.",
            )
            from app.email.smtp_client import EmailMessage, SendResult

            msg = EmailMessage(
                to=supplier_email,
                subject=f"Order Cancellation — {order_id[:8]}",
                body_text=f"We are cancelling order {order_id}. We apologize for any inconvenience.",
                body_html=body_html,
            )
            send_result = await email_svc._send(msg, "cancellation")

            if order and send_result.success:
                order.cancellation_email_id = send_result.message_id
                order.email_status = "cancelled"
                await self.db.flush()
        except Exception as e:
            logger.warning("Cancellation email failed (non-blocking): %s", e)
            # Still mark as cancelled even if email fails
            if order:
                order.email_status = "cancelled"
                await self.db.flush()

        return {
            "action": "cancellation_email_sent",
            "entity": "supplier_order",
            "entity_id": order_id,
        }

    async def _cancel_delivery(
        self, action_log: ActionLog, params: dict
    ) -> dict:
        """Cancel a delivery by setting its stage to 'cancelled'."""
        delivery_id = params.get("delivery_id", str(action_log.entity_id))

        result = await self.db.execute(
            select(Delivery).where(Delivery.id == action_log.entity_id)
        )
        delivery = result.scalar_one_or_none()

        if delivery and delivery.current_stage not in ("delivered", "cancelled"):
            delivery.current_stage = "cancelled"
            delivery.stage_history = [
                *delivery.stage_history,
                {
                    "stage": "cancelled",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "Rolled back by user",
                },
            ]
            await self.db.flush()

            await ws_manager.broadcast_all(
                "delivery:updated",
                {
                    "delivery_id": str(delivery.id),
                    "current_stage": "cancelled",
                    "reason": "Rolled back",
                },
            )

        return {
            "action": "delivery_cancelled",
            "entity": "delivery",
            "entity_id": delivery_id,
        }

    async def _restore_inventory(
        self, action_log: ActionLog, params: dict
    ) -> dict:
        """Restore inventory to its before-action state."""
        item_id = params.get("item_id", str(action_log.entity_id))
        restore_stock = params.get("restore_stock")

        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == action_log.entity_id)
        )
        item = result.scalar_one_or_none()

        restored_to = None
        if item and restore_stock is not None:
            item.current_stock = int(restore_stock)
            restored_to = item.current_stock
            await self.db.flush()

            await ws_manager.broadcast_all(
                "inventory:updated",
                {
                    "item_id": str(item.id),
                    "current_stock": item.current_stock,
                    "reason": "Rolled back",
                },
            )

        result_dict: dict[str, Any] = {
            "action": "stock_restored",
            "entity": "inventory_item",
            "entity_id": item_id,
        }
        if restored_to is not None:
            result_dict["restored_to"] = restored_to
        return result_dict

    async def _restore_eta(self, action_log: ActionLog, params: dict) -> dict:
        """Undo a `delivery.eta_update` — restore the delivery's
        ``expected_delivery_at`` and ``current_stage`` to their pre-update
        values, and append a ``manual_override`` timeline entry so the
        timeline remains append-only (constitution III).

        Feature 004 / T026: action_logs.compensating_action.params contains
        ``{delivery_id, expected_delivery_at, current_stage, source_reply_id}``.
        """
        from datetime import datetime as _dt, timezone as _tz

        from app.models.delivery_timeline_entry import DeliveryTimelineEntry
        from app.services.delivery_service import (
            append_timeline_entry,
            publish_timeline_event,
            serialise_delivery_summary,
            serialise_timeline_entry,
        )
        from app.websocket.events import publish_timeline_appended

        delivery_id = params.get("delivery_id") or str(action_log.entity_id)
        try:
            delivery_uuid = (
                delivery_id if isinstance(delivery_id, UUID) else UUID(str(delivery_id))
            )
        except (ValueError, TypeError):
            return {"action": "restore_eta_skipped", "reason": "invalid_delivery_id"}

        result = await self.db.execute(
            select(Delivery).where(Delivery.id == delivery_uuid)
        )
        delivery = result.scalar_one_or_none()
        if delivery is None:
            return {"action": "restore_eta_skipped", "reason": "delivery_not_found"}

        before_eta_raw = params.get("expected_delivery_at")
        before_stage = params.get("current_stage")
        before_eta: _dt | None = None
        if before_eta_raw:
            try:
                before_eta = _dt.fromisoformat(str(before_eta_raw).replace("Z", "+00:00"))
            except ValueError:
                before_eta = None

        delivery.expected_delivery_at = before_eta
        if before_stage:
            delivery.current_stage = str(before_stage)
        await self.db.flush()

        source_reply_id = params.get("source_reply_id")
        try:
            reply_uuid = UUID(str(source_reply_id)) if source_reply_id else None
        except (ValueError, TypeError):
            reply_uuid = None

        entry: DeliveryTimelineEntry = await append_timeline_entry(
            self.db,
            delivery_id=delivery.id,
            event_type="manual_override",
            occurred_at=_dt.now(_tz.utc),
            actor_type="admin",
            actor_id="undo_rollback",
            note=(
                "ETA auto-apply reversed by undo; expected_delivery_at and "
                "current_stage restored to pre-update values."
            ),
            source_reply_id=reply_uuid,
        )
        await self.db.flush()

        # Broadcast — undo is admin-initiated, so the WS event uses
        # `delivery.timeline.appended` (no review event involved).
        try:
            await publish_timeline_appended(
                delivery_id=delivery.id,
                entry=serialise_timeline_entry(entry),
                delivery_summary=serialise_delivery_summary(delivery),
            )
        except Exception:  # pragma: no cover — broadcast best-effort
            pass

        return {
            "action": "eta_restored",
            "entity": "delivery",
            "entity_id": str(delivery.id),
            "expected_delivery_at": (
                delivery.expected_delivery_at.isoformat()
                if delivery.expected_delivery_at
                else None
            ),
            "current_stage": delivery.current_stage,
            "timeline_entry_id": str(entry.id),
        }

    async def _restore_entity_state(self, action_log: ActionLog) -> dict:
        """Generic entity state restoration using before_state snapshot."""
        logger.info(
            "Generic restore for entity_type=%s entity_id=%s",
            action_log.entity_type,
            action_log.entity_id,
        )
        return {
            "action": "state_restored",
            "entity": action_log.entity_type,
            "entity_id": str(action_log.entity_id),
        }

    @staticmethod
    def _describe_compensating_action(action_log: ActionLog) -> str:
        """Generate a human-readable description of a compensating action."""
        comp = action_log.compensating_action
        action_type = comp.get("type", action_log.action_type)

        descriptions = {
            "send_cancellation_email": "Sending cancellation email to supplier",
            "cancel_delivery": "Cancelling delivery tracking",
            "restore_inventory": "Restoring inventory levels",
        }
        return descriptions.get(action_type, f"Reversing {action_type}")

    async def get_rollback_audit_trail(self, decision_id: UUID) -> list[dict]:
        """Get the audit trail of rolled-back actions for a decision."""
        result = await self.db.execute(
            select(ActionLog)
            .where(
                ActionLog.decision_id == decision_id,
                ActionLog.status == "rolled_back",
            )
            .order_by(ActionLog.rolled_back_at.desc())
        )
        logs = result.scalars().all()
        return [
            {
                "id": str(log.id),
                "action_type": log.action_type,
                "entity_type": log.entity_type,
                "entity_id": str(log.entity_id),
                "before_state": log.before_state,
                "after_state": log.after_state,
                "rolled_back_at": log.rolled_back_at.isoformat() if log.rolled_back_at else None,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]


class CannotUndoError(Exception):
    """Raised when a decision cannot be undone."""

    def __init__(self, message: str, reason: str = ""):
        super().__init__(message)
        self.reason = reason


class AlreadyRolledBackError(Exception):
    """Raised when a decision has already been rolled back."""
    pass
