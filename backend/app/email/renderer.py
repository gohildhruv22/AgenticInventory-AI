"""Jinja2 email template renderer with dark-theme HTML layout."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger("agenticinventory.email.renderer")

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _get_env() -> Environment:
    """Create a Jinja2 environment pointing at the templates directory."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_purchase_order(
    order_id: str,
    supplier_name: str,
    items: list[dict],
    total_cost: float,
    greeting: str = "",
    intro_paragraph: str = "",
    closing_paragraph: str = "",
    company_name: str = "AgenticInventory AI",
    # ── Supplier-facing fields (whitelist per spec 003-email-redesign FR-001) ──
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
    # ── Legacy kwargs (accepted for backwards-compat, intentionally ignored) ──
    # The supplier PO email MUST NOT expose internal AI signals
    # (confidence / forecast / decision rationale / urgency badges).
    # See specs/003-email-redesign/spec.md FR-002.
    urgency_note: str = "",  # noqa: ARG001
    stock_context: dict | None = None,  # noqa: ARG001
    forecast_context: dict | None = None,  # noqa: ARG001
    decision_context: dict | None = None,  # noqa: ARG001
    urgency_level: str = "normal",  # noqa: ARG001
    nominal_supplier_email: str = "",  # noqa: ARG001
) -> str:
    """Render a supplier-facing purchase order HTML email.

    Only order, pricing, fulfillment, and buyer-contact data are forwarded to
    the template. Any internal-AI signals (confidence, forecast inputs,
    decision rationale, urgency scores) passed by legacy callers are silently
    dropped per the email-redesign spec.
    """
    env = _get_env()
    template = env.get_template("purchase_order.html")
    computed_subtotal = (
        float(subtotal)
        if subtotal is not None
        else sum(
            float(it.get("quantity", 0)) * float(it.get("unit_cost", 0))
            for it in items
        )
    )
    return template.render(
        order_id=order_id,
        supplier_name=supplier_name,
        items=items,
        total_cost=total_cost,
        subtotal=computed_subtotal,
        tax_amount=float(tax_amount or 0),
        tax_label=tax_label,
        shipping_fee=float(shipping_fee or 0),
        greeting=greeting or f"Dear {supplier_name} Team,",
        intro_paragraph=intro_paragraph
        or f"We would like to place the following purchase order ({order_id[:8].upper()}). Please review the details below and confirm.",
        closing_paragraph=closing_paragraph
        or "Please confirm receipt of this order at your earliest convenience.",
        requested_delivery_date=requested_delivery_date,
        ship_to_address=ship_to_address,
        payment_terms=payment_terms,
        buyer_contact_name=buyer_contact_name,
        buyer_contact_email=buyer_contact_email,
        buyer_contact_phone=buyer_contact_phone,
        company_name=company_name,
    )


def render_admin_notification(
    subject: str,
    summary: str = "",
    order_id: str = "",
    item_name: str = "",
    supplier_name: str = "",
    total_cost: float = 0.0,
    decision: str = "",
    confidence: float = 0.0,
    action_required: bool = False,
    company_name: str = "AgenticInventory AI",
    # ── Explainability fields (spec 003-email-redesign US2) ──
    headline: str = "",
    rationale: str = "",
    rationale_source: str = "",  # "llm" | "fallback" | ""
    truncated: bool = False,
    decision_drivers: list[dict] | None = None,
    alternatives: list[dict] | None = None,
    dashboard_url: str = "",
) -> str:
    """Render an admin notification HTML email.

    When ``rationale`` is provided it is shown in the prominent "Why this
    decision" block (or "Summary" block when ``rationale_source == 'fallback'``).
    ``decision_drivers`` and ``alternatives`` populate the explainability
    sections below the rationale.
    """
    env = _get_env()
    template = env.get_template("admin_notification.html")
    return template.render(
        subject=subject,
        summary=summary,
        order_id=order_id,
        item_name=item_name,
        supplier_name=supplier_name,
        total_cost=total_cost,
        decision=decision,
        confidence=confidence,
        action_required=action_required,
        company_name=company_name,
        headline=headline,
        rationale=rationale,
        rationale_source=rationale_source,
        truncated=truncated,
        decision_drivers=decision_drivers or [],
        alternatives=alternatives or [],
        dashboard_url=dashboard_url,
    )


def render_kpi_report(
    report_date: str,
    order_volume: int = 0,
    total_spend: float = 0.0,
    arrivals: list[dict] | None = None,
    actions: list[dict] | None = None,
    dashboard_url: str = "",
    company_name: str = "AgenticInventory AI",
    # Detailed KPI fields (used by the redesigned light-theme digest)
    forecast_accuracy: float | None = None,
    avg_confidence: float | None = None,
    decisions_approved: int = 0,
    decisions_flagged: int = 0,
    decisions_rolled_back: int = 0,
    deliveries_completed: int = 0,
    deliveries_failed: int = 0,
    summary: str = "",
    highlights: list[str] | None = None,
    recommendations: list[str] | None = None,
    risk_alerts: list[str] | None = None,
    trends: list[str] | None = None,
    score: int = 0,
    industry_kpis: dict | None = None,
) -> str:
    """Render the daily KPI digest email — light theme, AI-insights-first.

    Headline counts + AI executive summary + recommendations + risks + KPIs
    + arrivals + actions. All sections gracefully hide when data is absent.
    """
    env = _get_env()
    template = env.get_template("kpi_report.html")
    arrivals = arrivals or []
    actions = actions or []
    highlights = highlights or []
    recommendations = recommendations or []
    risk_alerts = risk_alerts or []
    trends = trends or []
    industry_kpis = industry_kpis or {}
    quiet_day = order_volume == 0 and total_spend == 0 and not arrivals and not actions
    return template.render(
        report_date=report_date,
        order_volume=order_volume,
        total_spend=total_spend,
        arrivals=arrivals,
        actions=actions[:4],
        dashboard_url=dashboard_url,
        company_name=company_name,
        quiet_day=quiet_day,
        forecast_accuracy=forecast_accuracy,
        avg_confidence=avg_confidence,
        decisions_approved=decisions_approved,
        decisions_flagged=decisions_flagged,
        decisions_rolled_back=decisions_rolled_back,
        deliveries_completed=deliveries_completed,
        deliveries_failed=deliveries_failed,
        summary=summary,
        highlights=highlights[:5],
        recommendations=recommendations[:5],
        risk_alerts=risk_alerts[:4],
        trends=trends[:3],
        score=score,
        industry_kpis=industry_kpis,
    )


def render_cancellation(
    order_id: str,
    supplier_name: str,
    items: list[dict],
    total_cost: float,
    reason: str = "",
    greeting: str = "",
    company_name: str = "AgenticInventory AI",
) -> str:
    """Render an order cancellation HTML email."""
    env = _get_env()
    template = env.get_template("cancellation.html")
    return template.render(
        order_id=order_id,
        supplier_name=supplier_name,
        items=items,
        total_cost=total_cost,
        reason=reason,
        greeting=greeting or f"Dear {supplier_name},",
        company_name=company_name,
    )
