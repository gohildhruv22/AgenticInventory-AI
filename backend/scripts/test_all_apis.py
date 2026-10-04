"""Smoke-test every REST API route (+ optional live Groq LLM checks).

Run from backend/ with venv active:
    python scripts/test_all_apis.py
    python scripts/test_all_apis.py --groq   # include live LLM calls (slower)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from typing import Any

import httpx
from httpx import ASGITransport

# Ensure backend root is on path when run as script
sys.path.insert(0, ".")

from app.main import app  # noqa: E402

BASE = "/api/v1"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results: list[tuple[str, str, str]] = []  # name, status, detail


def record(name: str, ok: bool | None, detail: str = "") -> None:
    if ok is True:
        status = "pass"
        print(f"  [{PASS}] {name}" + (f" — {detail}" if detail else ""))
    elif ok is False:
        status = "fail"
        print(f"  [{FAIL}] {name}" + (f" — {detail}" if detail else ""))
    else:
        status = "skip"
        print(f"  [{SKIP}] {name}" + (f" — {detail}" if detail else ""))
    results.append((name, status, detail))


async def login(client: httpx.AsyncClient, email: str, password: str) -> bool:
    r = await client.post(
        f"{BASE}/auth/register",
        json={"email": email, "password": password, "name": "API Tester"},
    )
    if r.status_code == 201:
        return True
    r = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": password},
    )
    return r.status_code == 200


async def run_tests(include_groq: bool) -> int:
    email = f"apitest_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ── Health (no auth) ─────────────────────────────────────────────
        r = await client.get(f"{BASE}/health")
        record("GET /health", r.status_code == 200, f"status={r.json().get('status', '?')}")

        if not await login(client, email, password):
            record("auth login/register", False, f"HTTP {r.status_code}")
            return 1
        record("auth login/register", True)

        r = await client.get(f"{BASE}/auth/me")
        record("GET /auth/me", r.status_code == 200)

        # ── Inventory ────────────────────────────────────────────────────
        r = await client.get(f"{BASE}/inventory")
        record("GET /inventory", r.status_code == 200, f"items={len(r.json().get('items', []))}")
        items = r.json().get("items") or []
        item_id = items[0]["id"] if items else None

        r = await client.get(f"{BASE}/inventory/categories")
        record("GET /inventory/categories", r.status_code == 200)

        r = await client.get(f"{BASE}/inventory/stats")
        record("GET /inventory/stats", r.status_code == 200)

        r = await client.get(f"{BASE}/inventory/low-stock")
        record("GET /inventory/low-stock", r.status_code == 200)

        if item_id:
            r = await client.get(f"{BASE}/inventory/{item_id}")
            record("GET /inventory/{id}", r.status_code == 200)

        r = await client.post(f"{BASE}/inventory/seed")
        record("POST /inventory/seed", r.status_code in (200, 201))

        # ── Decisions ────────────────────────────────────────────────────
        r = await client.get(f"{BASE}/decisions")
        record("GET /decisions", r.status_code == 200)
        decisions = r.json().get("decisions") or []
        decision_id = decisions[0]["id"] if decisions else None

        r = await client.get(f"{BASE}/decisions/pending/list")
        record("GET /decisions/pending/list", r.status_code == 200)

        if decision_id:
            r = await client.get(f"{BASE}/decisions/{decision_id}")
            record("GET /decisions/{id}", r.status_code == 200)
            r = await client.get(f"{BASE}/decisions/{decision_id}/rollback-trail")
            record("GET /decisions/{id}/rollback-trail", r.status_code == 200)

        # ── Deliveries ───────────────────────────────────────────────────
        r = await client.get(f"{BASE}/deliveries")
        record("GET /deliveries", r.status_code == 200)
        deliveries = r.json().get("deliveries") or []
        delivery_id = deliveries[0]["id"] if deliveries else None

        if delivery_id:
            r = await client.get(f"{BASE}/deliveries/{delivery_id}")
            record("GET /deliveries/{id}", r.status_code == 200)
            r = await client.get(f"{BASE}/deliveries/{delivery_id}/timeline")
            record("GET /deliveries/{id}/timeline", r.status_code == 200)

        # ── ETA reviews ──────────────────────────────────────────────────
        r = await client.get(f"{BASE}/eta-reviews")
        record("GET /eta-reviews", r.status_code == 200, f"total={r.json().get('total', 0)}")
        reviews = r.json().get("items") or []
        review_id = reviews[0]["id"] if reviews else None
        if review_id:
            r = await client.get(f"{BASE}/eta-reviews/{review_id}")
            record("GET /eta-reviews/{id}", r.status_code == 200)

        # ── Reports ──────────────────────────────────────────────────────
        r = await client.get(f"{BASE}/reports")
        record("GET /reports", r.status_code == 200)
        reports = r.json().get("reports") or []
        report_id = reports[0]["id"] if reports else None

        r = await client.get(f"{BASE}/reports/dashboard")
        record("GET /reports/dashboard", r.status_code == 200)

        r = await client.get(f"{BASE}/reports/trends")
        record("GET /reports/trends", r.status_code == 200)

        r = await client.get(f"{BASE}/reports/suppliers")
        record("GET /reports/suppliers", r.status_code == 200)

        r = await client.get(f"{BASE}/reports/agents")
        record("GET /reports/agents", r.status_code == 200)

        if report_id:
            r = await client.get(f"{BASE}/reports/{report_id}")
            record("GET /reports/{id}", r.status_code == 200)

        r = await client.post(f"{BASE}/reports/seed-demo?days=1&refresh=true", json={})
        record("POST /reports/seed-demo", r.status_code == 200, f"created={r.json().get('total_created')}")

        # ── Orders ───────────────────────────────────────────────────────
        r = await client.get(f"{BASE}/orders")
        record("GET /orders", r.status_code == 200)
        orders = r.json().get("orders") or []
        if orders:
            r = await client.get(f"{BASE}/orders/{orders[0]['id']}")
            record("GET /orders/{id}", r.status_code == 200)

        # ── Pipeline ─────────────────────────────────────────────────────
        r = await client.post(f"{BASE}/pipeline/trigger", json={})
        ok_pipe = r.status_code == 202
        pipeline_id = r.json().get("pipeline_id") if ok_pipe else None
        record("POST /pipeline/trigger", ok_pipe)

        if pipeline_id:
            await asyncio.sleep(0.5)
            r = await client.get(f"{BASE}/pipeline/{pipeline_id}/status")
            record("GET /pipeline/{id}/status", r.status_code == 200)

        r = await client.get(f"{BASE}/pipeline/history")
        record("GET /pipeline/history", r.status_code == 200)

        # ── Monitoring ─────────────────────────────────────────────────
        r = await client.get(f"{BASE}/monitoring/status")
        record("GET /monitoring/status", r.status_code == 200)

        # Avoid /monitoring/trigger in smoke runs — it queues a full Groq pipeline (~4+ min).
        r = await client.post(f"{BASE}/monitoring/start", params={"interval": 300})
        record("POST /monitoring/start", r.status_code == 200)
        r = await client.post(f"{BASE}/monitoring/stop")
        record("POST /monitoring/stop", r.status_code == 200)

        # ── Settings ─────────────────────────────────────────────────────
        r = await client.get(f"{BASE}/settings/email/defaults")
        record("GET /settings/email/defaults", r.status_code == 200)

        r = await client.get(f"{BASE}/settings/email")
        # 404 when admin has not saved SMTP config yet — endpoint is still valid
        record(
            "GET /settings/email",
            r.status_code in (200, 404),
            "not configured" if r.status_code == 404 else "ok",
        )

        # ── Auth logout ────────────────────────────────────────────────────
        r = await client.post(f"{BASE}/auth/logout")
        record("POST /auth/logout", r.status_code == 200)

        # Re-login for Groq tests
        if include_groq:
            await login(client, email, password)

            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from app.models.forecast import Forecast
            from app.config import get_settings

            settings = get_settings()
            if not settings.GROQ_API_KEY:
                record("Groq API key", None, "GROQ_API_KEY not set — skipping LLM tests")
            else:
                async with AsyncSessionLocal() as db:
                    row = await db.execute(select(Forecast).limit(1))
                    forecast = row.scalar_one_or_none()

                if forecast:
                    r = await client.post(
                        f"{BASE}/decisions/evaluate",
                        json={"forecast_id": str(forecast.id)},
                        timeout=120.0,
                    )
                    ok = r.status_code == 200
                    detail = f"decision status={r.json().get('status')}" if ok else r.text[:120]
                    record("POST /decisions/evaluate (Groq)", ok, detail)
                else:
                    record("POST /decisions/evaluate (Groq)", None, "no forecasts in DB")

                r = await client.post(
                    f"{BASE}/reports/generate?send_email=false",
                    json={},
                    timeout=120.0,
                )
                ok = r.status_code == 200
                body: dict[str, Any] = r.json() if ok else {}
                ai = body.get("ai_summary_attached")
                record(
                    "POST /reports/generate (Groq AI summary)",
                    ok,
                    f"ai_attached={ai}" if ok else r.text[:120],
                )

                # Direct Groq ping (same as health_check_keys)
                try:
                    async with httpx.AsyncClient(timeout=30) as ext:
                        gr = await ext.post(
                            f"{settings.GROQ_BASE_URL}/chat/completions",
                            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                            json={
                                "model": settings.GROQ_LIGHTWEIGHT_MODEL,
                                "messages": [{"role": "user", "content": "Reply PONG only."}],
                                "max_tokens": 8,
                                "temperature": 0,
                            },
                        )
                    if gr.status_code == 200:
                        reply = gr.json()["choices"][0]["message"]["content"].strip()
                        record("Groq chat/completions direct", True, f"reply={reply!r}")
                    else:
                        record("Groq chat/completions direct", False, gr.text[:120])
                except Exception as exc:  # noqa: BLE001
                    record("Groq chat/completions direct", False, str(exc)[:120])

    passed = sum(1 for _, s, _ in results if s == "pass")
    failed = sum(1 for _, s, _ in results if s == "fail")
    skipped = sum(1 for _, s, _ in results if s == "skip")
    print()
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--groq",
        action="store_true",
        help="Run live Groq LLM tests (decision evaluate, report AI summary)",
    )
    args = parser.parse_args()
    print("API smoke tests" + (" (+ Groq LLM)" if args.groq else ""))
    print("-" * 50)
    code = asyncio.run(run_tests(include_groq=args.groq))
    sys.exit(code)


if __name__ == "__main__":
    main()
