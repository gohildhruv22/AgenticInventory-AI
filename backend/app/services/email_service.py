"""Email service — orchestrates SMTP sending, template rendering, and status tracking."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.email.renderer import render_admin_notification, render_kpi_report, render_purchase_order
from app.email.smtp_client import EmailMessage, SMTPClient, SendResult

logger = logging.getLogger("agenticinventory.services.email")


class EmailService:
    """High-level email sending service with template rendering and tracking.

    Supports both real SMTP sending (when configured) and simulation mode
    (when no SMTP settings are provided — logs the email instead).
    """

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_username: str = "",
        smtp_password: str = "",
        smtp_use_tls: bool = True,
        from_email: str = "",
        from_name: str = "AgenticInventory AI",
    ) -> None:
        self._smtp_host = smtp_host
        self._from_email = from_email
        self._from_name = from_name
        self._simulation_mode = not smtp_host

        if not self._simulation_mode:
            self._client = SMTPClient(
                host=smtp_host,
                port=smtp_port,
                username=smtp_username,
                password=smtp_password,
                use_tls=smtp_use_tls,
                from_email=from_email,
                from_name=from_name,
            )
            logger.info(
                "EmailService initialized: smtp_username=%s host=%s port=%s tls=%s",
                smtp_username,
                smtp_host,
                smtp_port,
                smtp_use_tls,
            )
        else:
            self._client = None
            logger.info("EmailService running in simulation mode (no SMTP configured)")

    @classmethod
    def from_settings(cls) -> "EmailService":
        """Create from application settings (simulation mode if no SMTP env vars)."""
        settings = get_settings()
        return cls(
            smtp_host=getattr(settings, "SMTP_HOST", ""),
            smtp_port=getattr(settings, "SMTP_PORT", 587),
            smtp_username=getattr(settings, "SMTP_USERNAME", ""),
            smtp_password=getattr(settings, "SMTP_PASSWORD", ""),
            smtp_use_tls=getattr(settings, "SMTP_USE_TLS", True),
            from_email=getattr(settings, "SMTP_FROM_EMAIL", ""),
            from_name=getattr(settings, "SMTP_FROM_NAME", "AgenticInventory AI"),
        )

    @classmethod
    async def from_db_or_settings(cls, db) -> "EmailService":  # noqa: ANN001 — AsyncSession
        """Prefer the most recently updated per-user EmailConfiguration row,
        otherwise fall back to env-level SMTP defaults.

        This is what background services / agents should use so the Settings
        page actually drives email delivery instead of being a no-op when the
        user provides their own SMTP credentials.

        Guardrail: if the DB row clearly contains placeholder/test data
        (very short password, username/host mismatch with env, etc.) we
        fall back to env so a single bad save in the Settings UI cannot
        permanently break autonomous email delivery.
        """
        try:
            from sqlalchemy import select

            from app.models.email_config import EmailConfiguration

            result = await db.execute(
                select(EmailConfiguration).order_by(EmailConfiguration.updated_at.desc()).limit(1)
            )
            config = result.scalar_one_or_none()
            if config and config.smtp_host and config.smtp_password_encrypted:
                env = get_settings()
                env_password = getattr(env, "SMTP_PASSWORD", "") or ""
                db_password = config.smtp_password_encrypted or ""

                # Gmail / most production SMTP app-passwords are >= 12 chars.
                # If the DB row's password is shorter than env's and env has a
                # real-looking password, env is almost certainly the correct one
                # (the DB row is likely placeholder data from a test save).
                if len(db_password) < 12 and len(env_password) >= 12:
                    logger.warning(
                        "DB email config appears to contain placeholder password "
                        "(len=%d); falling back to env SMTP credentials",
                        len(db_password),
                    )
                    return cls.from_settings()

                logger.info(
                    "EmailService using DB config: smtp_username=%s host=%s port=%s",
                    config.smtp_username,
                    config.smtp_host,
                    config.smtp_port,
                )
                return cls(
                    smtp_host=config.smtp_host,
                    smtp_port=config.smtp_port,
                    smtp_username=config.smtp_username,
                    smtp_password=config.smtp_password_encrypted,
                    smtp_use_tls=config.smtp_use_tls,
                    from_email=config.from_email,
                    from_name=config.from_name,
                )
        except Exception:  # noqa: BLE001 — DB read failure must never break email sending
            logger.exception("Failed to load EmailConfiguration from DB; falling back to env")
        return cls.from_settings()

    async def send_purchase_order(
        self,
        to_email: str,
        order_id: str,
        supplier_name: str,
        items: list[dict],
        total_cost: float,
        subject: str = "",
        greeting: str = "",
        intro_paragraph: str = "",
        closing_paragraph: str = "",
        # ── Supplier-facing fields (per spec 003 FR-001) ──
        requested_delivery_date: str = "",
        subtotal: float | None = None,
        tax_amount: float = 0.0,
        tax_label: str = "",
        shipping_fee: float = 0.0,
        ship_to_address: str = "",
        payment_terms: str = "",
        buyer_contact_name: str = "",
        buyer_contact_email: str = "",
        buyer_contact_phone: str = "",
        # ── Legacy kwargs accepted for back-compat, intentionally ignored ──
        # The supplier email MUST NOT leak internal AI signals — FR-002.
        urgency_note: str = "",  # noqa: ARG002
        stock_context: dict | None = None,  # noqa: ARG002
        forecast_context: dict | None = None,  # noqa: ARG002
        decision_context: dict | None = None,  # noqa: ARG002
        urgency_level: str = "normal",  # noqa: ARG002
        nominal_supplier_email: str = "",  # noqa: ARG002
    ) -> SendResult:
        """Send a supplier-facing purchase order email.

        Only order, pricing, fulfillment, and buyer-contact data are sent.
        Any internal-AI signals supplied by legacy callers are dropped before
        the email is composed (see specs/003-email-redesign FR-001/FR-002).
        """
        if not subject:
            category = items[0].get("category", "General") if items else "General"
            subject = f"Purchase Order {order_id[:8].upper()} — {category}"

        body_html = render_purchase_order(
            order_id=order_id,
            supplier_name=supplier_name,
            items=items,
            total_cost=total_cost,
            greeting=greeting,
            intro_paragraph=intro_paragraph,
            closing_paragraph=closing_paragraph,
            requested_delivery_date=requested_delivery_date,
            subtotal=subtotal,
            tax_amount=tax_amount,
            tax_label=tax_label,
            shipping_fee=shipping_fee,
            ship_to_address=ship_to_address,
            payment_terms=payment_terms,
            buyer_contact_name=buyer_contact_name,
            buyer_contact_email=buyer_contact_email,
            buyer_contact_phone=buyer_contact_phone,
        )

        items_text = "\n".join(
            f"  - {it.get('name', '?')} (SKU: {it.get('sku', '?')}) "
            f"x{it.get('quantity', 0)} @ ${it.get('unit_cost', 0):.2f}"
            for it in items
        )

        contact_lines: list[str] = []
        if ship_to_address:
            contact_lines.append(f"\nShip to:\n{ship_to_address}")
        if payment_terms:
            contact_lines.append(f"\nPayment terms: {payment_terms}")
        if buyer_contact_name or buyer_contact_email or buyer_contact_phone:
            contact_lines.append("\nBuyer contact:")
            if buyer_contact_name:
                contact_lines.append(f"  {buyer_contact_name}")
            if buyer_contact_email:
                contact_lines.append(f"  {buyer_contact_email}")
            if buyer_contact_phone:
                contact_lines.append(f"  {buyer_contact_phone}")
        contact_block = "\n".join(contact_lines) + "\n" if contact_lines else ""

        body_text = (
            f"{greeting or f'Dear {supplier_name} Team,'}\n\n"
            f"{intro_paragraph or f'We would like to place purchase order {order_id[:8].upper()}.'}\n\n"
            f"Order: {order_id}\n"
            f"Requested delivery: {requested_delivery_date or 'As soon as possible'}\n\n"
            f"Items:\n{items_text}\n\n"
            f"Total: ${total_cost:,.2f}\n"
            f"{contact_block}\n"
            f"{closing_paragraph or 'Please confirm receipt and the estimated delivery date.'}\n\n"
            f"Best regards,\n{self._from_name}"
        )

        msg = EmailMessage(
            to=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=self._from_email,
            from_name=self._from_name,
        )

        return await self._send(msg, "purchase_order")

    async def send_admin_notification(
        self,
        to_email: str,
        subject: str,
        summary: str = "",
        order_id: str = "",
        item_name: str = "",
        supplier_name: str = "",
        total_cost: float = 0.0,
        decision: str = "",
        confidence: float = 0.0,
        action_required: bool = False,
        # ── Explainability fields (spec 003-email-redesign US2) ──
        headline: str = "",
        rationale: str = "",
        rationale_source: str = "",  # "llm" | "fallback" | ""
        truncated: bool = False,
        decision_drivers: list[dict] | None = None,
        alternatives: list[dict] | None = None,
        dashboard_url: str = "",
    ) -> SendResult:
        """Send an admin notification email with optional explainability content."""
        body_html = render_admin_notification(
            subject=subject,
            summary=summary,
            order_id=order_id,
            item_name=item_name,
            supplier_name=supplier_name,
            total_cost=total_cost,
            decision=decision,
            confidence=confidence,
            action_required=action_required,
            headline=headline,
            rationale=rationale,
            rationale_source=rationale_source,
            truncated=truncated,
            decision_drivers=decision_drivers,
            alternatives=alternatives,
            dashboard_url=dashboard_url,
        )

        # Plain-text fallback body — mirrors the headline + rationale.
        text_lines: list[str] = []
        if headline:
            text_lines.append(headline)
            text_lines.append("")
        if rationale:
            text_lines.append(rationale)
            text_lines.append("")
        elif summary:
            text_lines.append(summary)
            text_lines.append("")
        if confidence:
            conf_pct = confidence * 100 if confidence <= 1 else confidence
            text_lines.append(f"Confidence: {conf_pct:.0f}%  ·  Decision: {decision or 'approve'}")
        if order_id:
            text_lines.append(f"Order: {order_id}")
        if item_name:
            text_lines.append(f"Item: {item_name}")
        if supplier_name:
            text_lines.append(f"Supplier: {supplier_name}")
        if total_cost:
            text_lines.append(f"Total: ${total_cost:,.2f}")
        if decision_drivers:
            text_lines.append("")
            text_lines.append("Decision drivers:")
            for d in decision_drivers:
                trend = f" ({d.get('trend')})" if d.get("trend") else ""
                text_lines.append(f"  - {d.get('label', '')}: {d.get('value', '')}{trend}")
        if alternatives:
            text_lines.append("")
            text_lines.append("Alternatives considered:")
            for a in alternatives:
                factor = f" — {a.get('deciding_factor')}" if a.get("deciding_factor") else ""
                text_lines.append(f"  - {a.get('option', '')}{factor}")
        text_lines.append("")
        text_lines.append("You can approve, undo, or cancel this order from your dashboard.")
        if dashboard_url:
            text_lines.append(dashboard_url)
        body_text = "\n".join(text_lines) if text_lines else summary

        msg = EmailMessage(
            to=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=self._from_email,
            from_name=self._from_name,
        )

        return await self._send(msg, "admin_notification")

    async def send_kpi_report(
        self,
        to_email: str,
        report_date: str,
        metrics: dict,
        summary_data: dict | None = None,
        # New daily-digest fields (spec 003-email-redesign US3)
        arrivals: list[dict] | None = None,
        actions: list[dict] | None = None,
        dashboard_url: str = "",
    ) -> SendResult:
        """Send the redesigned daily KPI digest email.

        Headline counts + AI executive summary + recommendations + risks +
        operational KPIs + arrivals + actions, in a light-theme palette
        matching the in-app Reports page. ``summary_data`` carries the AI
        summary; ``metrics`` provides the headline numbers and industry KPIs.
        """
        summary_data = summary_data or {}
        industry = (metrics or {}).get("industry_kpis") or {}

        body_html = render_kpi_report(
            report_date=report_date,
            order_volume=int(metrics.get("order_volume", 0) or 0),
            total_spend=float(metrics.get("total_spend", 0) or 0),
            arrivals=arrivals or [],
            actions=actions or [],
            dashboard_url=dashboard_url,
            forecast_accuracy=metrics.get("forecast_accuracy"),
            avg_confidence=metrics.get("avg_confidence_score") or metrics.get("avg_confidence"),
            decisions_approved=int(metrics.get("decisions_approved", 0) or 0),
            decisions_flagged=int(metrics.get("decisions_flagged", 0) or 0),
            decisions_rolled_back=int(metrics.get("decisions_rolled_back", 0) or 0),
            deliveries_completed=int(metrics.get("deliveries_completed", 0) or 0),
            deliveries_failed=int(metrics.get("deliveries_failed", 0) or 0),
            summary=summary_data.get("summary", "") or "",
            highlights=summary_data.get("highlights") or [],
            recommendations=summary_data.get("recommendations") or [],
            risk_alerts=summary_data.get("risk_alerts") or [],
            trends=summary_data.get("trends") or [],
            score=int(summary_data.get("score", 0) or 0),
            industry_kpis=industry,
        )

        score = summary_data.get("score")
        score_tag = f" · Score {score}/100" if isinstance(score, (int, float)) and score else ""
        subject = f"Daily KPI Report — {report_date}{score_tag}"

        # Plain-text fallback.
        spend = float(metrics.get("total_spend", 0) or 0)
        order_count = int(metrics.get("order_volume", 0) or 0)
        text_lines: list[str] = [
            f"Daily KPI Report — {report_date}",
            "",
            f"{order_count} order{'s' if order_count != 1 else ''} placed · ${spend:,.0f} spent",
        ]
        if summary_data.get("summary"):
            text_lines.extend(["", summary_data["summary"]])
        if summary_data.get("recommendations"):
            text_lines.extend(["", "Recommended actions:"])
            for r in summary_data["recommendations"]:
                text_lines.append(f"  - {r}")
        if summary_data.get("risk_alerts"):
            text_lines.extend(["", "Risk alerts:"])
            for r in summary_data["risk_alerts"]:
                text_lines.append(f"  ! {r}")
        if arrivals:
            text_lines.extend(["", "Stock arrivals today:"])
            for a in arrivals:
                supplier = f" from {a.get('supplier')}" if a.get("supplier") else ""
                text_lines.append(f"  - {a.get('name') or a.get('sku')} ({a.get('sku', '')}): +{a.get('qty', 0)} units{supplier}")
        if actions:
            text_lines.extend(["", "Potential actions:"])
            for act in actions[:4]:
                text_lines.append(f"  - [{(act.get('severity') or 'info').upper()}] {act.get('label', '')}")
                if act.get("reason"):
                    text_lines.append(f"      {act['reason']}")
        if dashboard_url:
            text_lines.extend(["", f"Open dashboard: {dashboard_url}"])
        body_text = "\n".join(text_lines)

        msg = EmailMessage(
            to=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=self._from_email,
            from_name=self._from_name,
        )

        return await self._send(msg, "kpi_report")

    async def test_connection(self) -> bool:
        """Test SMTP connectivity."""
        if self._simulation_mode:
            logger.info("Simulation mode — connection test always passes")
            return True
        return await self._client.test_connection()

    async def _send(self, msg: EmailMessage, email_type: str) -> SendResult:
        """Send or simulate sending an email."""
        if self._simulation_mode:
            logger.info(
                "[SIMULATION] Email %s: to=%s subject=%s\n--- Body ---\n%s\n--- End ---",
                email_type,
                msg.to,
                msg.subject,
                msg.body_text[:500],
            )
            return SendResult(
                success=True,
                message_id=msg.message_id,
                attempts=1,
                sent_at=datetime.now(timezone.utc),
            )

        return await self._client.send(msg)
