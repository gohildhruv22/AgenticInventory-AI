"""One-shot health check for all external API keys + SMTP.

Validates:
  - Groq (LLM)
  - NewsAPI
  - OpenWeather
  - Calendarific
  - SMTP (sends a real example email to the admin address)

Run from `backend/` with the venv active:
    python health_check_keys.py
"""
from __future__ import annotations

import asyncio
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from dotenv import load_dotenv

load_dotenv()

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"


def ok(name: str, detail: str = "") -> tuple[str, bool, str]:
    print(f"{GREEN}[ OK  ]{RESET} {name}  {detail}")
    return (name, True, detail)


def fail(name: str, detail: str) -> tuple[str, bool, str]:
    print(f"{RED}[FAIL ]{RESET} {name}  {detail}")
    return (name, False, detail)


async def check_groq() -> tuple[str, bool, str]:
    key = os.getenv("GROQ_API_KEY", "")
    base = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("GROQ_LIGHTWEIGHT_MODEL", "llama-3.1-8b-instant")
    if not key:
        return fail("Groq LLM", "GROQ_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": "Reply with the single word: PONG"}
                    ],
                    "max_tokens": 8,
                    "temperature": 0,
                },
            )
        if r.status_code != 200:
            return fail("Groq LLM", f"HTTP {r.status_code}: {r.text[:150]}")
        msg = r.json()["choices"][0]["message"]["content"].strip()
        return ok("Groq LLM", f"model={model} reply={msg!r}")
    except Exception as e:  # noqa: BLE001
        return fail("Groq LLM", f"{type(e).__name__}: {e}")


async def check_newsapi() -> tuple[str, bool, str]:
    key = os.getenv("NEWS_API_KEY", "")
    if not key:
        return fail("NewsAPI", "NEWS_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "pageSize": 1, "apiKey": key},
            )
        if r.status_code != 200:
            return fail("NewsAPI", f"HTTP {r.status_code}: {r.text[:150]}")
        data = r.json()
        total = data.get("totalResults", 0)
        return ok("NewsAPI", f"totalResults={total}")
    except Exception as e:  # noqa: BLE001
        return fail("NewsAPI", f"{type(e).__name__}: {e}")


async def check_openweather() -> tuple[str, bool, str]:
    key = os.getenv("OPENWEATHER_API_KEY", "")
    if not key:
        return fail("OpenWeather", "OPENWEATHER_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "Noida,IN", "appid": key, "units": "metric"},
            )
        if r.status_code != 200:
            return fail("OpenWeather", f"HTTP {r.status_code}: {r.text[:150]}")
        d = r.json()
        return ok(
            "OpenWeather",
            f"city={d.get('name')} temp={d.get('main', {}).get('temp')}°C",
        )
    except Exception as e:  # noqa: BLE001
        return fail("OpenWeather", f"{type(e).__name__}: {e}")


async def check_calendarific() -> tuple[str, bool, str]:
    key = os.getenv("CALENDARIFIC_API_KEY", "")
    if not key:
        return fail("Calendarific", "CALENDARIFIC_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://calendarific.com/api/v2/holidays",
                params={
                    "api_key": key,
                    "country": "IN",
                    "year": datetime.utcnow().year,
                },
            )
        if r.status_code != 200:
            return fail("Calendarific", f"HTTP {r.status_code}: {r.text[:150]}")
        data = r.json()
        count = len(data.get("response", {}).get("holidays", []))
        return ok("Calendarific", f"holidays_year={count}")
    except Exception as e:  # noqa: BLE001
        return fail("Calendarific", f"{type(e).__name__}: {e}")


def send_test_email(to_email: str, key_results: list[tuple[str, bool, str]]) -> tuple[str, bool, str]:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    user = os.getenv("SMTP_USERNAME", "")
    pwd = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    from_email = os.getenv("SMTP_FROM_EMAIL", user)
    from_name = os.getenv("SMTP_FROM_NAME", "AgenticInventory AI")

    if not (host and user and pwd and from_email):
        return fail("SMTP Email", "Missing one of SMTP_HOST / USERNAME / PASSWORD / FROM_EMAIL")

    # Build HTML body with the full health-check report
    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-weight:600;color:#0f172a;">{name}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">
            <span style="display:inline-block;padding:2px 10px;border-radius:9999px;
              font-size:11px;font-weight:700;letter-spacing:.04em;
              background:{'#dcfce7' if ok_ else '#fee2e2'};
              color:{'#166534' if ok_ else '#991b1b'};">
              {'OPERATIONAL' if ok_ else 'FAILED'}
            </span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#475569;font-size:12px;">{detail}</td>
        </tr>"""
        for name, ok_, detail in key_results
    )

    html = f"""
    <!doctype html>
    <html><body style="margin:0;padding:24px;background:#fafbfd;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;">
      <div style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;
                  border-radius:16px;overflow:hidden;
                  box-shadow:0 1px 3px rgba(15,23,42,.04),0 12px 28px rgba(15,23,42,.06);">
        <div style="padding:24px;background:linear-gradient(135deg,#7C3AED 0%,#EC4899 100%);">
          <p style="margin:0;color:rgba(255,255,255,.85);font-size:11px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;">
            AgenticInventory AI · Health Check
          </p>
          <h1 style="margin:8px 0 0;color:#ffffff;font-size:22px;font-weight:700;">
            All systems report
          </h1>
        </div>

        <div style="padding:24px;">
          <p style="margin:0 0 16px;color:#334155;font-size:14px;line-height:1.6;">
            This is an automated health-check email confirming that your SMTP relay is reachable
            <strong>and</strong> summarising the live status of every external API key used by the
            platform's AI agents.
          </p>

          <table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:13px;">
            <thead>
              <tr style="background:#f8fafc;">
                <th style="text-align:left;padding:10px 12px;color:#64748b;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Service</th>
                <th style="text-align:left;padding:10px 12px;color:#64748b;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Status</th>
                <th style="text-align:left;padding:10px 12px;color:#64748b;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Detail</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>

          <p style="margin:24px 0 0;padding:12px 16px;background:#f5f3ff;border-left:3px solid #7C3AED;
                    color:#5b21b6;font-size:12px;border-radius:8px;">
            <strong>SMTP relay:</strong> {host}:{port} (TLS={'on' if use_tls else 'off'})<br/>
            <strong>Sent at:</strong> {datetime.utcnow().isoformat(timespec='seconds')}Z
          </p>
        </div>

        <div style="padding:16px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;
                    color:#94a3b8;font-size:11px;text-align:center;">
          AgenticInventory AI · Automated diagnostic · Do not reply
        </div>
      </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "AgenticInventory AI — API & SMTP health check"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText("AgenticInventory AI health check (HTML email required).", "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=ctx)
                server.ehlo()
            server.login(user, pwd)
            server.sendmail(from_email, [to_email], msg.as_string())
        return ok("SMTP Email", f"sent to {to_email} via {host}:{port}")
    except Exception as e:  # noqa: BLE001
        return fail("SMTP Email", f"{type(e).__name__}: {e}")


async def main() -> int:
    to_email = os.getenv(
        "HEALTHCHECK_TO_EMAIL",
        os.getenv("ADMIN_NOTIFICATION_EMAIL", ""),
    ) or "gohil.rohitbhai@maqsoftware.com"

    print(f"\n{BOLD}{CYAN}AgenticInventory AI — Key & SMTP Health Check{RESET}")
    print(f"{CYAN}Sending example email to:{RESET} {to_email}\n")

    results = await asyncio.gather(
        check_groq(),
        check_newsapi(),
        check_openweather(),
        check_calendarific(),
    )
    results = list(results)
    results.append(send_test_email(to_email, results))

    print()
    total = len(results)
    passed = sum(1 for _, ok_, _ in results if ok_)
    color = GREEN if passed == total else (YELLOW if passed else RED)
    print(f"{BOLD}{color}Summary: {passed}/{total} checks passed{RESET}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
