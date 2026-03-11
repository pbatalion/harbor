from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.settings import Settings


def render_digest_html(settings: Settings, analysis: dict[str, Any]) -> str:
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("digest.html")

    email_digest = analysis.get("email_digest", {})
    return template.render(
        subject=settings.delivery.digest_subject_prefix,
        summary=email_digest.get("summary", ""),
        urgent_items=analysis.get("urgent_items", []),
        day_plan=analysis.get("day_plan", ""),
        draft_actions=email_digest.get("draft_actions", []),
    )


def _write_local_preview(settings: Settings, html: str, run_id: str) -> str:
    outbox = Path(settings.delivery.outbox_dir)
    if not outbox.is_absolute():
        root = Path(__file__).resolve().parent.parent.parent
        outbox = root / outbox
    outbox.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = outbox / f"digest-{stamp}-{run_id[:8]}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)


def send_email_digest(settings: Settings, analysis: dict[str, Any], run_id: str) -> str:
    html = render_digest_html(settings, analysis)

    if not settings.delivery_email_enabled:
        return _write_local_preview(settings, html, run_id)

    if not (settings.smtp_host and settings.digest_email_to and settings.digest_email_from):
        return _write_local_preview(settings, html, run_id)

    message = MIMEMultipart("alternative")
    message["Subject"] = f"{settings.delivery.digest_subject_prefix}"
    message["From"] = settings.digest_email_from
    message["To"] = settings.digest_email_to
    message.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.digest_email_from, [settings.digest_email_to], message.as_string())

    return "smtp_sent"
