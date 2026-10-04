"""Report service — aggregates daily KPI metrics from database tables."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, cast, func, select, Numeric
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_decision import AgentDecision
from app.models.delivery import Delivery
from app.models.forecast import Forecast
from app.models.inventory_item import InventoryItem
from app.models.kpi_report import KPIReport
from app.models.supplier_order import SupplierOrder
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.services.report")


class ReportService:
    """Aggregates daily KPI metrics and persists KPIReport records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_daily_report(self, report_date: date | None = None) -> KPIReport:
        """Generate or update daily KPI report for the given date."""
        target_date = report_date or date.today()

        # Check if report already exists for this date
        result = await self.db.execute(
            select(KPIReport).where(KPIReport.report_date == target_date)
        )
        existing = result.scalar_one_or_none()

        metrics = await self._aggregate_metrics(target_date)

        if existing:
            for key, value in metrics.items():
                setattr(existing, key, value)
            await self.db.flush()
            report = existing
            logger.info("Updated KPI report for %s", target_date)
        else:
            report = KPIReport(report_date=target_date, **metrics)
            self.db.add(report)
            await self.db.flush()
            logger.info("Created KPI report for %s id=%s", target_date, report.id)

        # Broadcast dashboard update
        await ws_manager.broadcast_all("kpi:update", {
            "report_date": str(target_date),
            "order_volume": metrics["order_volume"],
            "total_spend": float(metrics["total_spend"]),
            "forecast_accuracy": float(metrics["forecast_accuracy"]) if metrics["forecast_accuracy"] else None,
            "avg_confidence_score": float(metrics["avg_confidence_score"]) if metrics["avg_confidence_score"] else None,
            "decisions_approved": metrics["decisions_approved"],
            "decisions_flagged": metrics["decisions_flagged"],
        })

        return report

    async def attach_ai_summary(self, report: KPIReport) -> dict:
        """Run the Reporting & KPI agent and persist its summary into report_data.

        The agent receives:
          * the report's headline counts and KPIs,
          * a short list of *named* low-stock items, flagged decisions, and
            recent deliveries so it can ground recommendations in specifics,
          * a 7-day baseline so trend statements can be made.

        Returns the structured summary dict (also stored under
        ``report.report_data['ai_summary']``).
        """
        industry = (report.report_data or {}).get("industry_kpis", {}) or {}

        # ── Named context: low-stock items, flagged decisions, deliveries ──
        low_stock_items: list[dict] = []
        try:
            rows = (await self.db.execute(
                select(InventoryItem)
                .where(
                    InventoryItem.is_active == True,  # noqa: E712
                    InventoryItem.current_stock <= InventoryItem.reorder_threshold,
                )
                .order_by(InventoryItem.current_stock.asc())
                .limit(5)
            )).scalars().all()
            for it in rows:
                low_stock_items.append({
                    "name": it.name,
                    "sku": it.sku,
                    "current_stock": int(it.current_stock or 0),
                    "threshold": int(it.reorder_threshold or 0),
                    "supplier": it.supplier_email or "",
                })
        except Exception:  # noqa: BLE001
            logger.exception("AI summary: low-stock lookup failed")

        flagged_items: list[dict] = []
        try:
            from app.models.supplier_order import SupplierOrder
            dec_rows = (await self.db.execute(
                select(AgentDecision, InventoryItem)
                .join(
                    InventoryItem,
                    AgentDecision.inventory_item_id == InventoryItem.id,
                    isouter=True,
                )
                .where(
                    AgentDecision.status.in_(["flagged", "pending_review"]),
                    func.date(AgentDecision.created_at) == report.report_date,
                )
                .order_by(AgentDecision.created_at.desc())
                .limit(5)
            )).all()
            for dec, item in dec_rows:
                trace = dec.reasoning_trace if isinstance(dec.reasoning_trace, dict) else {}
                meta = dec.metadata_ or {}
                flagged_items.append({
                    "item_name": item.name if item else "Unknown item",
                    "sku": item.sku if item else "",
                    "confidence": round(float(dec.confidence_level or 0) * 100, 1),
                    "estimated_cost": float(
                        meta.get("estimated_cost")
                        or trace.get("estimated_cost")
                        or 0
                    ),
                    "reasoning": str(
                        trace.get("reasoning") or trace.get("summary") or ""
                    )[:160],
                })
        except Exception:  # noqa: BLE001
            logger.exception("AI summary: flagged lookup failed")

        recent_deliveries: list[dict] = []
        try:
            from app.models.supplier_order import SupplierOrder
            del_rows = (await self.db.execute(
                select(Delivery, SupplierOrder, InventoryItem)
                .join(SupplierOrder, SupplierOrder.id == Delivery.order_id)
                .join(AgentDecision, AgentDecision.id == SupplierOrder.decision_id)
                .join(
                    InventoryItem,
                    InventoryItem.id == AgentDecision.inventory_item_id,
                    isouter=True,
                )
                .order_by(Delivery.updated_at.desc())
                .limit(5)
            )).all()
            for d, so, it in del_rows:
                recent_deliveries.append({
                    "item": (it.name if it else (so.supplier_name or "Order")),
                    "stage": d.current_stage,
                    "supplier": so.supplier_name or "",
                    "expected": str(d.expected_delivery_at) if d.expected_delivery_at else None,
                })
        except Exception:  # noqa: BLE001
            logger.exception("AI summary: deliveries lookup failed")

        # ── 7-day baseline for trend statements ──
        weekly = {"weekly_avg_orders": None, "weekly_avg_spend": None}
        try:
            wk_rows = (await self.db.execute(
                select(
                    func.avg(KPIReport.order_volume).label("avg_orders"),
                    func.avg(KPIReport.total_spend).label("avg_spend"),
                ).where(
                    KPIReport.report_date < report.report_date,
                ).order_by(KPIReport.report_date.desc()).limit(7)
            )).one()
            if wk_rows.avg_orders is not None:
                weekly["weekly_avg_orders"] = round(float(wk_rows.avg_orders), 1)
            if wk_rows.avg_spend is not None:
                weekly["weekly_avg_spend"] = round(float(wk_rows.avg_spend), 2)
        except Exception:  # noqa: BLE001
            logger.exception("AI summary: weekly baseline lookup failed")

        metrics = {
            "report_date": str(report.report_date),
            "order_volume": report.order_volume,
            "total_spend": float(report.total_spend),
            "forecast_accuracy": float(report.forecast_accuracy) if report.forecast_accuracy else None,
            "avg_confidence_score": float(report.avg_confidence_score) if report.avg_confidence_score else None,
            "decisions_approved": report.decisions_approved,
            "decisions_flagged": report.decisions_flagged,
            "decisions_rolled_back": report.decisions_rolled_back,
            "deliveries_completed": report.deliveries_completed,
            "deliveries_failed": report.deliveries_failed,
            "email_delivery_rate": float(report.email_delivery_rate) if report.email_delivery_rate else None,
            "low_stock_items": low_stock_items,
            "flagged_items": flagged_items,
            "recent_deliveries": recent_deliveries,
            **weekly,
            **industry,
        }

        from app.agents.reporting_kpi import ReportingKPIAgent
        agent = ReportingKPIAgent()
        try:
            kpi_summary = await agent.summarize(metrics)
        finally:
            await agent.close()

        summary_data = {
            "summary": kpi_summary.summary,
            "highlights": kpi_summary.highlights,
            "trends": kpi_summary.trends,
            "recommendations": kpi_summary.recommendations,
            "risk_alerts": kpi_summary.risk_alerts,
            "score": kpi_summary.score,
        }
        report.report_data = {
            **(report.report_data or {}),
            "ai_summary": summary_data,
            "ai_context": {
                "low_stock_items": low_stock_items,
                "flagged_items": flagged_items,
                "recent_deliveries": recent_deliveries,
                **weekly,
            },
        }
        await self.db.flush()
        return summary_data

    async def email_report(self, report: KPIReport, to_email: str) -> bool:
        """Send the daily KPI digest email — light theme, AI-insights-first.

        Includes headline counts, the AI executive summary + recommendations
        + risks, the operational KPI tiles, today's arrivals, and a short
        list of potential manager actions.
        """
        report_data = report.report_data or {}
        ai_summary = report_data.get("ai_summary") or {}
        industry = report_data.get("industry_kpis") or {}

        metrics = {
            "order_volume": report.order_volume,
            "total_spend": float(report.total_spend),
            "forecast_accuracy": float(report.forecast_accuracy) if report.forecast_accuracy else None,
            "avg_confidence_score": float(report.avg_confidence_score) if report.avg_confidence_score else None,
            "decisions_approved": report.decisions_approved,
            "decisions_flagged": report.decisions_flagged,
            "decisions_rolled_back": report.decisions_rolled_back,
            "deliveries_completed": report.deliveries_completed,
            "deliveries_failed": report.deliveries_failed,
            "industry_kpis": industry,
        }

        # ── Arrivals: deliveries with actual_delivery_at on today ──
        arrivals: list[dict] = []
        try:
            today = date.today()
            arr_rows = (await self.db.execute(
                select(Delivery, SupplierOrder)
                .join(SupplierOrder, SupplierOrder.id == Delivery.order_id)
                .where(func.date(Delivery.actual_delivery_at) == today)
                .order_by(Delivery.actual_delivery_at.desc())
                .limit(10)
            )).all()
            for delivery, sup_order in arr_rows:
                # Each supplier_order.items is a JSON list of line items.
                line_items = sup_order.items or []
                if not isinstance(line_items, list):
                    line_items = []
                for li in line_items[:5]:
                    if not isinstance(li, dict):
                        continue
                    arrivals.append({
                        "name": li.get("name") or li.get("item_name") or "",
                        "sku": li.get("sku") or "",
                        "qty": li.get("quantity") or li.get("qty") or 0,
                        "supplier": sup_order.supplier_name,
                    })
        except Exception:  # noqa: BLE001
            logger.exception("Daily digest: failed to gather arrivals (non-blocking)")
            arrivals = []

        # ── Potential actions: low-stock items + flagged decisions ──
        actions: list[dict] = []
        try:
            from app.config import get_settings as _get_settings
            env_settings = _get_settings()
            frontend_base = (
                getattr(env_settings, "FRONTEND_BASE_URL", "")
                or "http://localhost:5173"
            ).rstrip("/")

            # 1. Inventory items at or below reorder threshold
            low_rows = (await self.db.execute(
                select(InventoryItem)
                .where(
                    InventoryItem.is_active == True,  # noqa: E712
                    InventoryItem.current_stock <= InventoryItem.reorder_threshold,
                )
                .order_by(
                    (InventoryItem.current_stock * 1.0
                     / func.greatest(InventoryItem.reorder_threshold, 1)).asc()
                )
                .limit(2)
            )).scalars().all()
            for it in low_rows:
                severity = "critical" if it.current_stock == 0 else "warning"
                actions.append({
                    "label": f"Restock {it.name}",
                    "reason": (
                        f"Stock at {it.current_stock} units "
                        f"(threshold {it.reorder_threshold})."
                    ),
                    "severity": severity,
                    "url": f"{frontend_base}/inventory?sku={it.sku}",
                })

            # 2. Flagged decisions awaiting admin review
            flagged_rows = (await self.db.execute(
                select(AgentDecision)
                .where(AgentDecision.status.in_(["flagged", "pending_review"]))
                .order_by(AgentDecision.created_at.desc())
                .limit(max(0, 4 - len(actions)))
            )).scalars().all()
            for dec in flagged_rows:
                actions.append({
                    "label": "Review flagged order",
                    "reason": (
                        f"Confidence {(float(dec.confidence_level or 0) * 100):.0f}% "
                        f"— needs your sign-off."
                    ),
                    "severity": "warning",
                    "url": f"{frontend_base}/agents?decision={dec.id}",
                })
        except Exception:  # noqa: BLE001
            logger.exception("Daily digest: failed to gather actions (non-blocking)")
            actions = []
            frontend_base = "http://localhost:5173"

        dashboard_url = f"{frontend_base}/"

        from app.services.email_service import EmailService
        email_svc = await EmailService.from_db_or_settings(self.db)
        result = await email_svc.send_kpi_report(
            to_email=to_email,
            report_date=str(report.report_date),
            metrics=metrics,
            summary_data=ai_summary,
            arrivals=arrivals,
            actions=actions[:4],
            dashboard_url=dashboard_url,
        )
        if result.success:
            report.email_sent = True
            report.email_sent_at = datetime.now(timezone.utc)
            existing = report.email_recipients or []
            if to_email not in existing:
                report.email_recipients = [*existing, to_email]
            await self.db.flush()
            logger.info("Daily digest %s emailed to %s", report.id, to_email)
        else:
            logger.error("Failed to email daily digest %s: %s", report.id, result.error)
        return result.success


    async def get_dashboard_running_totals(self) -> dict:
        """Get real-time running totals for dashboard display."""
        today = date.today()

        # Order volume and spend today
        order_result = await self.db.execute(
            select(
                func.count().label("volume"),
                func.coalesce(func.sum(SupplierOrder.total_cost), 0).label("spend"),
            ).where(func.date(SupplierOrder.created_at) == today)
        )
        order_row = order_result.one()

        # Decisions today
        decision_result = await self.db.execute(
            select(
                func.count().filter(AgentDecision.status == "approved").label("approved"),
                func.count().filter(AgentDecision.status == "flagged").label("flagged"),
                func.count().filter(AgentDecision.status == "rejected").label("rejected"),
                func.avg(AgentDecision.confidence_level).label("avg_confidence"),
            ).where(func.date(AgentDecision.created_at) == today)
        )
        dec_row = decision_result.one()

        # Active deliveries
        active_del = await self.db.execute(
            select(func.count()).where(
                Delivery.current_stage.notin_(["delivered", "failed"])
            )
        )

        # Low stock
        low_stock = await self.db.execute(
            select(func.count()).where(
                InventoryItem.is_active == True,
                InventoryItem.current_stock <= InventoryItem.reorder_threshold,
            )
        )

        # Forecast accuracy (last 7 days)
        accuracy = await self._compute_forecast_accuracy(7)

        return {
            "order_volume": order_row.volume,
            "total_spend": float(order_row.spend),
            "forecast_accuracy": accuracy,
            "avg_confidence": float(dec_row.avg_confidence) if dec_row.avg_confidence else None,
            "decisions_approved": dec_row.approved,
            "decisions_flagged": dec_row.flagged,
            "active_deliveries": active_del.scalar() or 0,
            "low_stock_count": low_stock.scalar() or 0,
        }

    async def get_trend_data(self, days: int = 7) -> list[dict]:
        """Get daily metrics for trending charts."""
        result = await self.db.execute(
            select(KPIReport)
            .order_by(KPIReport.report_date.desc())
            .limit(days)
        )
        reports = list(result.scalars().all())
        reports.reverse()  # Oldest first for charts

        return [
            {
                "date": str(r.report_date),
                "order_volume": r.order_volume,
                "total_spend": float(r.total_spend),
                "forecast_accuracy": float(r.forecast_accuracy) if r.forecast_accuracy else None,
                "avg_confidence": float(r.avg_confidence_score) if r.avg_confidence_score else None,
                "decisions_approved": r.decisions_approved,
                "decisions_flagged": r.decisions_flagged,
                "deliveries_completed": r.deliveries_completed,
                "cost_savings": float(r.cost_savings_estimate) if r.cost_savings_estimate else 0,
            }
            for r in reports
        ]

    async def get_supplier_performance(self) -> list[dict]:
        """Get supplier performance metrics for chart display."""
        result = await self.db.execute(
            select(
                SupplierOrder.supplier_name,
                func.count().label("order_count"),
                func.sum(SupplierOrder.total_cost).label("total_value"),
                func.avg(
                    case(
                        (SupplierOrder.email_status == "sent", 1),
                        else_=0,
                    )
                ).label("success_rate"),
            )
            .group_by(SupplierOrder.supplier_name)
            .order_by(func.count().desc())
            .limit(10)
        )
        rows = result.all()
        return [
            {
                "supplier": row.supplier_name,
                "orders": row.order_count,
                "value": float(row.total_value or 0),
                "success_rate": round(float(row.success_rate or 0) * 100, 1),
            }
            for row in rows
        ]

    async def get_agent_activity_distribution(self) -> list[dict]:
        """Get agent decision activity for pie chart."""
        result = await self.db.execute(
            select(
                AgentDecision.agent_type,
                func.count().label("count"),
            )
            .group_by(AgentDecision.agent_type)
            .order_by(func.count().desc())
        )
        rows = result.all()
        return [
            {"agent": row.agent_type, "count": row.count}
            for row in rows
        ]

    async def _aggregate_metrics(self, target_date: date) -> dict:
        """Aggregate all metrics for a specific date."""
        # Orders
        order_result = await self.db.execute(
            select(
                func.count().label("volume"),
                func.coalesce(func.sum(SupplierOrder.total_cost), 0).label("spend"),
            ).where(func.date(SupplierOrder.created_at) == target_date)
        )
        order_row = order_result.one()

        # Decisions
        dec_result = await self.db.execute(
            select(
                func.count().filter(AgentDecision.status == "approved").label("approved"),
                func.count().filter(AgentDecision.status == "flagged").label("flagged"),
                func.count().filter(AgentDecision.status == "rolled_back").label("rolled_back"),
                func.avg(AgentDecision.confidence_level).label("avg_conf"),
            ).where(func.date(AgentDecision.created_at) == target_date)
        )
        dec_row = dec_result.one()

        # Deliveries
        del_result = await self.db.execute(
            select(
                func.count().filter(Delivery.current_stage == "delivered").label("completed"),
                func.count().filter(Delivery.current_stage == "failed").label("failed"),
            ).where(func.date(Delivery.created_at) == target_date)
        )
        del_row = del_result.one()

        # Agent activity
        agent_result = await self.db.execute(
            select(
                AgentDecision.agent_type,
                func.count().label("count"),
            )
            .where(func.date(AgentDecision.created_at) == target_date)
            .group_by(AgentDecision.agent_type)
        )
        agent_activity = {row.agent_type: row.count for row in agent_result.all()}

        # Supplier performance
        supplier_result = await self.db.execute(
            select(
                SupplierOrder.supplier_name,
                func.count().label("orders"),
                func.sum(SupplierOrder.total_cost).label("spend"),
            )
            .where(func.date(SupplierOrder.created_at) == target_date)
            .group_by(SupplierOrder.supplier_name)
        )
        supplier_perf = {
            row.supplier_name: {"orders": row.orders, "spend": float(row.spend or 0)}
            for row in supplier_result.all()
        }

        # Email delivery rate
        email_result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(SupplierOrder.email_status == "sent").label("sent"),
            ).where(func.date(SupplierOrder.created_at) == target_date)
        )
        email_row = email_result.one()
        email_rate = (
            Decimal(str(round(email_row.sent / email_row.total * 100, 2)))
            if email_row.total > 0
            else None
        )

        # ── Industry-standard procurement & inventory KPIs ──────────────
        # OTIF (On-Time In-Full) proxy: deliveries completed / total
        total_deliveries = del_row.completed + del_row.failed
        otif_rate = (
            round(del_row.completed / total_deliveries * 100, 1)
            if total_deliveries > 0
            else None
        )

        # Decision automation rate
        total_decisions = dec_row.approved + dec_row.flagged + dec_row.rolled_back
        automation_rate = (
            round(dec_row.approved / total_decisions * 100, 1)
            if total_decisions > 0
            else None
        )

        # Rollback rate
        rollback_rate = (
            round(dec_row.rolled_back / total_decisions * 100, 1)
            if total_decisions > 0
            else None
        )

        # Stockout & low-stock health (inventory snapshot, not date-bound)
        stock_result = await self.db.execute(
            select(
                func.count().filter(InventoryItem.is_active == True).label("active_skus"),
                func.count().filter(
                    (InventoryItem.is_active == True) & (InventoryItem.current_stock == 0)
                ).label("stockouts"),
                func.count().filter(
                    (InventoryItem.is_active == True)
                    & (InventoryItem.current_stock <= InventoryItem.reorder_threshold)
                    & (InventoryItem.current_stock > 0)
                ).label("at_risk"),
            )
        )
        stock_row = stock_result.one()
        stockout_rate = (
            round(stock_row.stockouts / stock_row.active_skus * 100, 1)
            if stock_row.active_skus > 0
            else None
        )

        # Spend by category (today)
        cat_result = await self.db.execute(
            select(
                InventoryItem.category,
                func.coalesce(func.sum(SupplierOrder.total_cost), 0).label("spend"),
                func.count(SupplierOrder.id).label("orders"),
            )
            .select_from(SupplierOrder)
            .join(AgentDecision, SupplierOrder.decision_id == AgentDecision.id)
            .join(InventoryItem, AgentDecision.inventory_item_id == InventoryItem.id)
            .where(func.date(SupplierOrder.created_at) == target_date)
            .group_by(InventoryItem.category)
            .order_by(func.sum(SupplierOrder.total_cost).desc())
            .limit(5)
        )
        spend_by_category = [
            {
                "category": row.category,
                "spend": float(row.spend or 0),
                "orders": row.orders,
            }
            for row in cat_result.all()
        ]

        # Top suppliers by spend (today)
        top_suppliers = [
            {"supplier": k, "orders": v["orders"], "spend": v["spend"]}
            for k, v in sorted(
                supplier_perf.items(), key=lambda x: x[1]["spend"], reverse=True
            )[:5]
        ]

        # Average order value
        avg_order_value = (
            round(float(order_row.spend) / order_row.volume, 2)
            if order_row.volume > 0
            else 0.0
        )

        # Perfect order rate: delivered + email sent + not rolled back
        # (proxy: orders where email_status='sent' AND no rollback link)
        perfect_order_rate = email_rate  # close proxy for now

        # Forecast accuracy
        accuracy = await self._compute_forecast_accuracy(1, target_date)

        # Feature 004 — ETA agent counts:
        #   auto_applied_eta_count: applied ETA updates persisted today
        #     (one row per action_logs entry with action_type='delivery.eta_update'
        #      and status='executed').
        #   pending_review_count: total open `eta_review_items` (not bounded by
        #     `target_date` because the review queue is a live backlog).
        from app.models.action_log import ActionLog
        from app.models.eta_review_item import EtaReviewItem

        auto_applied_row = await self.db.execute(
            select(func.count(ActionLog.id)).where(
                ActionLog.action_type == "delivery.eta_update",
                ActionLog.status == "executed",
                func.date(ActionLog.created_at) == target_date,
            )
        )
        auto_applied_eta_count = int(auto_applied_row.scalar() or 0)

        pending_review_row = await self.db.execute(
            select(func.count(EtaReviewItem.id)).where(
                EtaReviewItem.resolution_state == "pending"
            )
        )
        pending_review_count = int(pending_review_row.scalar() or 0)

        # Bundle non-column KPIs into report_data so they survive without
        # requiring a DB migration.
        industry_kpis = {
            "otif_rate": otif_rate,
            "automation_rate": automation_rate,
            "rollback_rate": rollback_rate,
            "stockout_rate": stockout_rate,
            "active_skus": stock_row.active_skus,
            "stockout_count": stock_row.stockouts,
            "at_risk_count": stock_row.at_risk,
            "avg_order_value": avg_order_value,
            "perfect_order_rate": float(perfect_order_rate) if perfect_order_rate is not None else None,
            "spend_by_category": spend_by_category,
            "top_suppliers": top_suppliers,
            "total_decisions": total_decisions,
            "total_deliveries": total_deliveries,
            # Feature 004 — supplier-reply ETA agent KPIs.
            "auto_applied_eta_count": auto_applied_eta_count,
            "pending_review_count": pending_review_count,
        }

        return {
            "order_volume": order_row.volume,
            "total_spend": Decimal(str(float(order_row.spend))),
            "forecast_accuracy": Decimal(str(accuracy)) if accuracy else None,
            "avg_confidence_score": Decimal(str(round(float(dec_row.avg_conf), 2))) if dec_row.avg_conf else None,
            "decisions_approved": dec_row.approved,
            "decisions_flagged": dec_row.flagged,
            "decisions_rolled_back": dec_row.rolled_back,
            "deliveries_completed": del_row.completed,
            "deliveries_failed": del_row.failed,
            "supplier_performance": supplier_perf,
            "agent_activity": agent_activity,
            "email_delivery_rate": email_rate,
            "cost_savings_estimate": None,
            "report_data": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "industry_kpis": industry_kpis,
            },
        }

    async def _compute_forecast_accuracy(
        self, days: int, ref_date: date | None = None
    ) -> float | None:
        """Compute forecast accuracy over the given period."""
        target = ref_date or date.today()
        result = await self.db.execute(
            select(func.avg(Forecast.confidence_score))
            .where(func.date(Forecast.created_at) <= target)
            .order_by(Forecast.created_at.desc())
            .limit(days * 10)
        )
        avg = result.scalar()
        return round(float(avg), 2) if avg else None

    async def generate_and_email_daily_report(
        self,
        admin_email: str,
        report_date: date | None = None,
    ) -> KPIReport:
        """Generate daily report, produce AI summary, and email to admin."""
        report = await self.generate_daily_report(report_date)
        try:
            await self.attach_ai_summary(report)
        except Exception:
            logger.exception("Failed to attach AI summary to KPI report")
        try:
            await self.email_report(report, admin_email)
        except Exception:
            logger.exception("Failed to email daily KPI report")
        return report
