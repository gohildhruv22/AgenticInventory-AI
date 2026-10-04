from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.email_config import EmailConfiguration
from app.models.user import User
from app.schemas.settings import EmailConfigCreate, EmailConfigResponse, EmailConfigUpdate
from app.services.email_service import EmailService

router = APIRouter(prefix="/settings", tags=["settings"])


class EmailDefaultsResponse(BaseModel):
    """Server-side SMTP defaults from the .env, used to pre-fill the Settings form."""

    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_tls: bool
    from_email: str
    from_name: str
    admin_notification_email: str | None = None
    supplier_override_email: str | None = None
    password_configured: bool


@router.get("/email/defaults", response_model=EmailDefaultsResponse)
async def get_email_defaults(user: User = Depends(get_current_user)):
    """Expose env-level SMTP defaults so the UI can pre-fill on first setup."""
    s = get_settings()
    return EmailDefaultsResponse(
        smtp_host=getattr(s, "SMTP_HOST", "") or "",
        smtp_port=getattr(s, "SMTP_PORT", 587) or 587,
        smtp_username=getattr(s, "SMTP_USERNAME", "") or "",
        smtp_use_tls=bool(getattr(s, "SMTP_USE_TLS", True)),
        from_email=getattr(s, "SMTP_FROM_EMAIL", "") or "",
        from_name=getattr(s, "SMTP_FROM_NAME", "AgenticInventory AI") or "AgenticInventory AI",
        admin_notification_email=getattr(s, "ADMIN_NOTIFICATION_EMAIL", "") or None,
        supplier_override_email=getattr(s, "SUPPLIER_OVERRIDE_EMAIL", "") or None,
        password_configured=bool(getattr(s, "SMTP_PASSWORD", "")),
    )


@router.get("/email", response_model=EmailConfigResponse)
async def get_email_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EmailConfiguration).where(EmailConfiguration.user_id == user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("Email configuration not found")
    return config


@router.put("/email", response_model=EmailConfigResponse)
async def upsert_email_config(
    body: EmailConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EmailConfiguration).where(EmailConfiguration.user_id == user.id)
    )
    config = result.scalar_one_or_none()

    data = body.model_dump()
    # Map raw password into the storage column (only when provided). When the user
    # is updating other settings and leaves the password blank, we preserve the
    # previously stored value so the SMTP credentials don't get wiped.
    submitted_password = data.pop("smtp_password", None)

    # For first-time setup we transparently fall back to the server's .env-level
    # SMTP defaults whenever a field is missing/empty. This lets users save
    # supplier mappings and thresholds without having to re-enter every SMTP
    # detail manually — and surfaces a clear error only when truly nothing is
    # available to send mail with.
    env = get_settings()
    if not config:
        if not data.get("smtp_host"):
            data["smtp_host"] = getattr(env, "SMTP_HOST", "") or ""
        if not data.get("smtp_username"):
            data["smtp_username"] = getattr(env, "SMTP_USERNAME", "") or ""
        if not data.get("from_email"):
            data["from_email"] = (
                getattr(env, "SMTP_FROM_EMAIL", "")
                or data.get("smtp_username")
                or ""
            )
        if not submitted_password:
            submitted_password = getattr(env, "SMTP_PASSWORD", "") or None

        # Final guardrail: we still need *something* to write to the NOT NULL columns.
        missing: list[str] = []
        if not data.get("smtp_host"):
            missing.append("smtp_host")
        if not data.get("smtp_username"):
            missing.append("smtp_username")
        if not data.get("from_email"):
            missing.append("from_email")
        if not submitted_password:
            missing.append("smtp_password")
        if missing:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail=(
                    "Missing SMTP credentials for initial setup: "
                    + ", ".join(missing)
                    + ". Either fill them in the form or set them in backend/.env."
                ),
            )

    if config:
        for field, value in data.items():
            setattr(config, field, value)
        if submitted_password:
            config.smtp_password_encrypted = submitted_password
    else:
        config = EmailConfiguration(
            user_id=user.id,
            smtp_password_encrypted=submitted_password,
            **data,
        )
        db.add(config)

    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/email", status_code=204)
async def delete_email_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove the user's email configuration."""
    result = await db.execute(
        select(EmailConfiguration).where(EmailConfiguration.user_id == user.id)
    )
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)
        await db.flush()
    return None


class TestEmailRequest(BaseModel):
    to_email: EmailStr


@router.post("/email/test")
async def test_email(
    body: TestEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a test email using the user's configured SMTP settings."""
    result = await db.execute(
        select(EmailConfiguration).where(EmailConfiguration.user_id == user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("Email configuration not found. Please configure SMTP settings first.")

    service = EmailService(
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_username=config.smtp_username,
        smtp_password=config.smtp_password_encrypted,
        smtp_use_tls=config.smtp_use_tls,
        from_email=config.from_email,
        from_name=config.from_name,
    )

    # Verify SMTP connectivity first so we can surface a clear error.
    ok = await service.test_connection()
    if not ok:
        return {
            "success": False,
            "message": "Failed to connect to SMTP server. Check host, port, credentials, and TLS settings.",
        }

    # Actually send a real test email so the recipient can verify delivery.
    result = await service.send_admin_notification(
        to_email=body.to_email,
        subject="AgenticInventory AI — SMTP Test Email",
        summary=(
            "This is a test message from AgenticInventory AI. "
            "If you're reading this, your SMTP configuration is working correctly."
        ),
        decision="SMTP Test",
        confidence=100.0,
        action_required=False,
    )

    if result.success:
        return {
            "success": True,
            "message": f"Test email sent successfully to {body.to_email}",
        }
    return {
        "success": False,
        "message": f"SMTP connected but send failed: {result.error or 'unknown error'}",
    }
