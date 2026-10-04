"""Order service — creates supplier orders from approved decisions and triggers email sending."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.admin_rationale import (
    AdminRationaleAgent,
    AdminRationaleContext,
    DecisionDriver,
)
from app.agents.supplier_email import SupplierEmailAgent
from app.config import get_settings
from app.models.action_log import ActionLog
from app.models.agent_decision import AgentDecision
from app.models.delivery import Delivery
from app.models.forecast import Forecast
from app.models.inventory_item import InventoryItem
from app.models.supplier_order import SupplierOrder
from app.services.email_service import EmailService
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.services.order")

# Default category → supplier mapping (used when no DB config exists)
DEFAULT_SUPPLIER_MAPPINGS: dict[str, dict] = {
    "Electronics": {"name": "TechParts Global", "email": "orders@techparts.example.com"},
    "Raw Materials": {"name": "Industrial Supply Co", "email": "orders@industrialsupply.example.com"},
    "Packaging": {"name": "PackRight Solutions", "email": "orders@packright.example.com"},
    "Office Supplies": {"name": "OfficeMax Pro", "email": "orders@officemaxpro.example.com"},
}
DEFAULT_SUPPLIER = {"name": "General Supplier", "email": "orders@generalsupplier.example.com"}


class OrderService:
    """Creates SupplierOrder records from approved AgentDecisions,
    resolves supplier info, and triggers email sending with AI-composed content."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_order_from_decision(
        self,
        decision_id: UUID,
        supplier_mappings: dict | None = None,
        admin_email: str = "",
    ) -> SupplierOrder:
        """Create a supplier order from an approved decision and send emails.

        1. Load decision and inventory item.
        2. Resolve supplier from category mapping.
        3. AI-compose the email content via SupplierEmailAgent.
        4. Persist SupplierOrder record.
        5. Send purchase order email to supplier.
        6. Send admin notification email.
        7. Broadcast via WebSocket.
        """
        # 1. Load decision
        result = await self.db.execute(
            select(AgentDecision).where(AgentDecision.id == decision_id)
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        if decision.status != "approved":
            raise ValueError(
                f"Decision {decision_id} is '{decision.status}', expected 'approved'"
            )

        # Load inventory item
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == decision.inventory_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"Inventory item {decision.inventory_item_id} not found")

        # 2. Resolve supplier
        mappings = supplier_mappings or DEFAULT_SUPPLIER_MAPPINGS
        supplier_info = mappings.get(item.category, DEFAULT_SUPPLIER)
        # Keep the realistic supplier name on the order for explainability,
        # but route the actual delivery to the SUPPLIER_OVERRIDE_EMAIL when
        # configured — by default this funnels every category to the admin
        # inbox so demos / staging never bounce.
        supplier_name = supplier_info["name"]
        nominal_supplier_email = item.supplier_email or supplier_info["email"]
        settings = get_settings()
        override_email = getattr(settings, "SUPPLIER_OVERRIDE_EMAIL", "") or ""
        supplier_email = override_email or nominal_supplier_email

        # Build items list for the order
        order_qty = decision.metadata_.get("approved_order_qty", 0)
        estimated_cost = decision.metadata_.get("estimated_cost", 0.0)
        items_list = [
            {
                "name": item.name,
                "sku": item.sku,
                "category": item.category,
                "quantity": order_qty,
                "unit_cost": float(item.unit_cost),
            }
        ]
        total_cost = Decimal(str(estimated_cost)) if estimated_cost else Decimal(str(order_qty)) * item.unit_cost

        # 4. Persist SupplierOrder
        order = SupplierOrder(
            decision_id=decision_id,
            supplier_name=supplier_name,
            supplier_email=supplier_email,
            items=items_list,
            total_cost=total_cost,
            email_status="composing",
        )
        self.db.add(order)
        await self.db.flush()

        order_id_str = str(order.id)
        logger.info(
            "Order created: id=%s decision=%s supplier=%s cost=%s",
            order_id_str, decision_id, supplier_name, total_cost,
        )

        # 3. AI-compose email content
        decision_context = {
            "decision": decision.reasoning_trace.get("decision", "approve"),
            "confidence": float(decision.confidence_level or 0),
            "reasoning": decision.reasoning_trace.get("reasoning", ""),
            "risk_factors": decision.reasoning_trace.get("risk_factors", []),
        }

        # Load the forecast referenced by this decision so we can include
        # predicted demand + confidence + reasoning directly in the supplier
        # email (makes the order self-explanatory).
        forecast_context: dict = {}
        if decision.forecast_id:
            forecast_result = await self.db.execute(
                select(Forecast).where(Forecast.id == decision.forecast_id)
            )
            forecast_row = forecast_result.scalar_one_or_none()
            if forecast_row:
                forecast_context = {
                    "predicted_demand": forecast_row.predicted_demand,
                    "confidence_score": float(forecast_row.confidence_score or 0),
                    "suggested_order_qty": forecast_row.suggested_order_qty,
                    "reasoning": forecast_row.reasoning or "",
                    "trend_direction": forecast_row.trend_direction or "",
                }

        order_data = {
            "order_id": order_id_str,
            "item_name": item.name,
            "sku": item.sku,
            "category": item.category,
            "quantity": order_qty,
            "unit_cost": float(item.unit_cost),
            "total_cost": float(total_cost),
            "current_stock": item.current_stock,
            "reorder_threshold": item.reorder_threshold,
        }

        agent = SupplierEmailAgent()
        try:
            composition = await agent.compose(order_data, decision_context, supplier_name)
        finally:
            await agent.close()

        # 5. Send purchase order email
        order.email_status = "sending"
        await self.db.flush()

        email_svc = await EmailService.from_db_or_settings(self.db)

        urgency = "critical" if item.current_stock == 0 else (
            "high" if item.current_stock <= item.reorder_threshold else "normal"
        )
        urgency_note = ""
        if urgency == "critical":
            urgency_note = "CRITICAL: Stock is at zero — expedited shipping requested."
        elif urgency == "high":
            urgency_note = "Stock is below reorder threshold — priority processing appreciated."

        # ── Compute expected delivery date from item.lead_time_days ──
        # The supplier email shows this date and the Deliveries page uses it
        # to auto-advance the tracking stage (no supplier confirmation needed).
        lead_days = int(item.lead_time_days or 7)
        ordered_at = datetime.now(timezone.utc)
        expected_delivery_at = ordered_at + timedelta(days=lead_days)
        expected_delivery_str = expected_delivery_at.strftime("%B %d, %Y")

        send_result = await email_svc.send_purchase_order(
            to_email=supplier_email,
            order_id=order_id_str,
            supplier_name=supplier_name,
            items=items_list,
            total_cost=float(total_cost),
            subject=composition.subject,
            greeting=f"Dear {supplier_name} Team,",
            intro_paragraph=composition.body_text.split("\n")[0] if composition.body_text else "",
            requested_delivery_date=expected_delivery_str,
            urgency_note=urgency_note,
            stock_context={
                "current_stock": item.current_stock,
                "reorder_threshold": item.reorder_threshold,
                "safety_stock": item.safety_stock,
                "lead_time_days": item.lead_time_days,
            },
            forecast_context=forecast_context,
            decision_context={
                "decision": decision_context["decision"],
                "confidence": decision_context["confidence"],
                "reasoning": decision_context["reasoning"],
            },
            urgency_level=urgency,
            nominal_supplier_email=nominal_supplier_email,
        )

        if send_result.success:
            order.email_status = "sent"
            order.email_message_id = send_result.message_id
            logger.info("Purchase order email sent: %s", send_result.message_id)
        else:
            order.email_status = "failed"
            order.retry_count = send_result.attempts
            logger.error("Purchase order email failed after %d attempts: %s", send_result.attempts, send_result.error)

        await self.db.flush()

        # ── 5b. Create Delivery tracking record ──────────────────
        # Every order gets a Delivery row so the Deliveries page can track
        # the shipment. The stage is auto-advanced based on elapsed time vs
        # `expected_delivery_at` (see DeliveryService.recompute_stage), so
        # no manual supplier-side confirmation is required.
        try:
            existing_delivery = await self.db.execute(
                select(Delivery).where(Delivery.order_id == order.id)
            )
            if existing_delivery.scalar_one_or_none() is None:
                stage_history = [
                    {
                        "stage": "ordered",
                        "at": ordered_at.isoformat(),
                        "note": f"PO emailed to {supplier_name}",
                    }
                ]
                delivery = Delivery(
                    order_id=order.id,
                    current_stage="ordered",
                    stage_history=stage_history,
                    expected_delivery_at=expected_delivery_at,
                    simulation_config={
                        "lead_time_days": lead_days,
                        "ordered_at": ordered_at.isoformat(),
                        "auto_advance": True,
                    },
                )
                self.db.add(delivery)
                await self.db.flush()
                logger.info(
                    "Delivery created: id=%s order=%s expected_delivery_at=%s",
                    delivery.id, order.id, expected_delivery_at.isoformat(),
                )
        except Exception:
            logger.exception("Failed to create Delivery record (non-blocking)")

        # 6. Send admin notification (best-effort) — with LLM-grounded rationale
        if admin_email:
            try:
                # Build the decision-driver list from forecast + stock signals
                # so the rationale agent has structured context to ground on.
                drivers: list[DecisionDriver] = []
                if item.current_stock is not None and item.reorder_threshold is not None:
                    drivers.append(DecisionDriver(
                        label="Current stock",
                        value=f"{item.current_stock} units (threshold {item.reorder_threshold})",
                        trend="down" if item.current_stock < item.reorder_threshold else "flat",
                    ))
                if item.lead_time_days:
                    drivers.append(DecisionDriver(
                        label="Lead time",
                        value=f"{item.lead_time_days} days",
                    ))
                if forecast_context.get("predicted_demand"):
                    fc_conf_raw = float(forecast_context.get("confidence_score") or 0)
                    fc_conf = fc_conf_raw * 100 if fc_conf_raw <= 1 else fc_conf_raw
                    fc_trend = forecast_context.get("trend_direction") or ""
                    norm_trend = (
                        "up" if "up" in fc_trend.lower() or "rise" in fc_trend.lower()
                        else "down" if "down" in fc_trend.lower() or "fall" in fc_trend.lower()
                        else "flat"
                    )
                    drivers.append(DecisionDriver(
                        label="Demand forecast",
                        value=f"{forecast_context['predicted_demand']} units predicted ({fc_conf:.0f}% confidence)",
                        trend=norm_trend,
                    ))
                drivers.append(DecisionDriver(
                    label="Order value",
                    value=f"${float(total_cost):,.2f}",
                ))

                # Build the explainable rationale via LLM (with deterministic fallback).
                rationale_agent = AdminRationaleAgent()
                try:
                    rationale_ctx = AdminRationaleContext(
                        order_id=order_id_str,
                        item_name=item.name,
                        supplier_name=supplier_name,
                        total_cost=float(total_cost),
                        confidence=float(decision.confidence_level or 0),
                        decision=decision.reasoning_trace.get("decision", "approve"),
                        drivers=drivers,
                    )
                    rationale_result = await rationale_agent.generate(rationale_ctx)
                finally:
                    await rationale_agent.close()

                drivers_payload = [
                    {"label": d.label, "value": d.value, "trend": d.trend}
                    for d in drivers
                ]

                # Build a deep-link to the in-app decision detail page.
                env_settings = get_settings()
                frontend_base = (
                    getattr(env_settings, "FRONTEND_BASE_URL", "")
                    or "http://localhost:5173"
                ).rstrip("/")
                dashboard_url = f"{frontend_base}/agents?decision={decision_id}"

                conf_pct = float(decision.confidence_level or 0) * 100
                needs_review = conf_pct < 60

                await email_svc.send_admin_notification(
                    to_email=admin_email,
                    subject=f"Order Placed: {item.name} (PO {order_id_str[:8].upper()})",
                    summary="",  # superseded by rationale; kept for backwards compat
                    order_id=order_id_str,
                    item_name=item.name,
                    supplier_name=supplier_name,
                    total_cost=float(total_cost),
                    decision=decision.reasoning_trace.get("decision", "approve"),
                    confidence=float(decision.confidence_level or 0),
                    action_required=needs_review,
                    headline=rationale_result.headline,
                    rationale=rationale_result.rationale,
                    rationale_source=rationale_result.source,
                    truncated=rationale_result.truncated,
                    decision_drivers=drivers_payload,
                    alternatives=[],  # populated when multi-supplier scoring is added
                    dashboard_url=dashboard_url,
                )
                if rationale_result.source != "llm":
                    logger.info(
                        "Admin email rationale source=%s (order=%s)",
                        rationale_result.source,
                        order_id_str,
                    )
            except Exception:
                logger.exception("Admin notification email failed (non-blocking)")

        # 7. Record action log for rollback support
        action_log = ActionLog(
            agent_type="supplier_email",
            action_type="create_order",
            entity_type="supplier_order",
            entity_id=order.id,
            before_state={"exists": False},
            after_state={
                "order_id": order_id_str,
                "supplier_name": supplier_name,
                "supplier_email": supplier_email,
                "total_cost": float(total_cost),
                "email_status": order.email_status,
                "items": items_list,
            },
            compensating_action={
                "type": "send_cancellation_email",
                "params": {
                    "supplier_email": supplier_email,
                    "order_id": order_id_str,
                    "supplier_name": supplier_name,
                    "template": "cancellation",
                },
                "restore_entity": True,
            },
            decision_id=decision_id,
            status="executed",
            reasoning_trace={
                "reason": f"Order created for {item.name}",
                "order_qty": order_qty,
                "estimated_cost": float(total_cost),
            },
        )
        self.db.add(action_log)
        await self.db.flush()

        # 8. Broadcast via WebSocket
        await ws_manager.broadcast_all(
            "order:created",
            {
                "order_id": order_id_str,
                "decision_id": str(decision_id),
                "item_id": str(item.id),
                "item_name": item.name,
                "supplier_name": supplier_name,
                "supplier_email": supplier_email,
                "total_cost": float(total_cost),
                "email_status": order.email_status,
                "quantity": order_qty,
            },
        )

        return order

    async def get_order(self, order_id: UUID) -> SupplierOrder | None:
        """Retrieve a single order by ID."""
        result = await self.db.execute(
            select(SupplierOrder).where(SupplierOrder.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_order_by_decision(self, decision_id: UUID) -> SupplierOrder | None:
        """Retrieve the order linked to a specific decision."""
        result = await self.db.execute(
            select(SupplierOrder).where(SupplierOrder.decision_id == decision_id)
        )
        return result.scalar_one_or_none()

    async def list_orders(self, limit: int = 50) -> list[SupplierOrder]:
        """List recent orders."""
        result = await self.db.execute(
            select(SupplierOrder)
            .order_by(SupplierOrder.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_orders_by_status(self, status: str, limit: int = 50) -> list[SupplierOrder]:
        """List orders filtered by email status."""
        result = await self.db.execute(
            select(SupplierOrder)
            .where(SupplierOrder.email_status == status)
            .order_by(SupplierOrder.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
