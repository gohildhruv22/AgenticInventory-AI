import math
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.kpi_report import KPIReport
from app.models.agent_decision import AgentDecision
from app.models.delivery import Delivery
from app.models.inventory_item import InventoryItem
from app.models.user import User
from app.schemas.report import DashboardMetrics, KPIReportResponse, ReportListResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(KPIReport)

    if date_from:
        query = query.where(KPIReport.report_date >= date_from)
    if date_to:
        query = query.where(KPIReport.report_date <= date_to)

    query = query.order_by(KPIReport.report_date.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    reports = result.scalars().all()

    return ReportListResponse(
        reports=[KPIReportResponse.model_validate(r) for r in reports],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ReportService(db)
    totals = await svc.get_dashboard_running_totals()
    return DashboardMetrics(**totals)


@router.get("/trends")
async def get_trends(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get daily metric trends for charts."""
    svc = ReportService(db)
    return await svc.get_trend_data(days)


@router.get("/suppliers")
async def get_supplier_performance(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get supplier performance metrics for charts."""
    svc = ReportService(db)
    return await svc.get_supplier_performance()


@router.get("/agents")
async def get_agent_activity(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get agent activity distribution for charts."""
    svc = ReportService(db)
    return await svc.get_agent_activity_distribution()


@router.post("/generate")
async def generate_daily_report(
    background_tasks: BackgroundTasks,
    send_email: bool = Query(True, description="Also email the report to the configured admin"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Trigger daily report generation.

    Always runs the AI summary agent so the in-app report is insight-rich,
    even when email is disabled. When ``send_email`` is true (default) the
    report is also emailed to ``ADMIN_NOTIFICATION_EMAIL`` if configured.
    """
    svc = ReportService(db)
    report = await svc.generate_daily_report()

    ai_attached = False
    ai_error: str | None = None
    try:
        await svc.attach_ai_summary(report)
        ai_attached = True
    except Exception as exc:  # noqa: BLE001
        ai_error = str(exc)[:240]

    emailed = False
    email_error: str | None = None
    if send_email:
        admin_email = (getattr(get_settings(), "ADMIN_NOTIFICATION_EMAIL", "") or "").strip()
        if admin_email:
            try:
                emailed = await svc.email_report(report, admin_email)
            except Exception as exc:  # noqa: BLE001
                email_error = str(exc)[:240]

    await db.commit()

    ai_summary = (report.report_data or {}).get("ai_summary") or {}
    return {
        "status": "generated",
        "report_id": str(report.id),
        "date": str(report.report_date),
        "ai_summary_attached": ai_attached,
        "ai_error": ai_error,
        "emailed": emailed,
        "email_error": email_error,
        "score": ai_summary.get("score"),
        "summary": ai_summary.get("summary"),
    }


@router.post("/seed-demo")
async def seed_demo_reports(
    days: int = Query(7, ge=1, le=30, description="How many past days of reports to backfill"),
    refresh: bool = Query(False, description="If true, regenerate existing reports as well"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Backfill the last ``days`` days of KPI reports for demo purposes.

    Idempotent — existing reports are skipped unless ``refresh=true``.
    Each generated report is enriched with an AI summary so the page has
    plenty of insight-rich content to browse during demos.
    """
    from datetime import timedelta

    svc = ReportService(db)
    today = date.today()
    created: list[dict] = []
    skipped: list[str] = []
    failed: list[dict] = []

    for offset in range(days, 0, -1):
        target = today - timedelta(days=offset - 1)
        existing = (await db.execute(
            select(KPIReport).where(KPIReport.report_date == target)
        )).scalar_one_or_none()

        if existing and not refresh:
            skipped.append(str(target))
            continue

        try:
            report = await svc.generate_daily_report(report_date=target)
            try:
                await svc.attach_ai_summary(report)
            except Exception:  # noqa: BLE001
                pass
            created.append({
                "date": str(target),
                "report_id": str(report.id),
                "score": ((report.report_data or {}).get("ai_summary") or {}).get("score"),
            })
        except Exception as exc:  # noqa: BLE001
            failed.append({"date": str(target), "error": str(exc)[:240]})

    await db.commit()
    return {
        "status": "ok",
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total_created": len(created),
    }


class EmailReportRequest(BaseModel):
    to_email: EmailStr | None = None


@router.post("/{report_id}/email")
async def email_existing_report(
    report_id: str,
    body: EmailReportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Send (or re-send) a previously generated KPI report to an address.

    Defaults to the ``ADMIN_NOTIFICATION_EMAIL`` configured in the environment
    when no recipient is specified.
    """
    result = await db.execute(select(KPIReport).where(KPIReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report not found")

    to_email = (body.to_email if body else None) or (
        getattr(get_settings(), "ADMIN_NOTIFICATION_EMAIL", "") or ""
    ).strip()
    if not to_email:
        raise HTTPException(
            status_code=400,
            detail="No recipient address provided and ADMIN_NOTIFICATION_EMAIL is not set.",
        )

    svc = ReportService(db)
    if not (report.report_data or {}).get("ai_summary"):
        try:
            await svc.attach_ai_summary(report)
        except Exception:  # noqa: BLE001
            pass
    ok = await svc.email_report(report, to_email)
    await db.commit()
    return {"success": ok, "to": to_email}


@router.get("/{report_id}", response_model=KPIReportResponse)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(KPIReport).where(KPIReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report not found")
    return report
