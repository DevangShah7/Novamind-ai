"""
SMTP mailer for NovaMind.

Two modes:
  - Dev stub (default when SMTP_HOST is unset): writes a one-line
    summary to stdout AND appends a full record to logs/dev-mail.log,
    so the verification/reset URLs are visible in tests.
  - Real SMTP: uses stdlib `smtplib` + `email.message.EmailMessage`.
    Works with any SMTP relay (Gmail with app passwords, SendGrid,
    Mailgun, AWS SES, Postmark, etc.).

Callers do not branch on mode: `send_email(to, subject, text, html)`
always works. The mailer logs a single line per send so operators
can see what was actually sent (or stubbed) without trawling
dev-mail.log for a debug session.

The dev stub is deliberately noisy so it cannot be confused with a
silent drop in production. The log path comes from
`AUDIT_LOG_DIR` (set in main.py) and falls back to ./logs.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .config import settings

logger = logging.getLogger("novamind.mailer")


def _dev_log_path() -> Path:
    """Where to write the dev-mode mail log if SMTP is not configured.

    Order: $AUDIT_LOG_DIR (set by main.py to a platform-aware path),
    then ./logs alongside the rest of the app's local state.
    """
    base = os.environ.get("AUDIT_LOG_DIR") or os.path.join(
        os.getcwd(), "logs"
    )
    os.makedirs(base, exist_ok=True)
    return Path(base) / "dev-mail.log"


def _is_configured() -> bool:
    """SMTP is "configured" when at minimum the host is set."""
    return bool(getattr(settings, "SMTP_HOST", ""))


def _format_envelope(
    to: Iterable[str],
) -> Tuple[str, list]:
    if isinstance(to, str):
        return to, [to]
    to_list = [t.strip() for t in to if t and t.strip()]
    if not to_list:
        raise ValueError("send_email called with no recipients")
    return to_list[0], to_list


def _build_message(
    to_addrs: list,
    subject: str,
    text: str,
    html: Optional[str] = None,
) -> EmailMessage:
    """Compose a multipart EmailMessage with the configured From header."""
    from_email = settings.SMTP_FROM or "noreply@novamind.ai"
    from_name = getattr(settings, "SMTP_FROM_NAME", "NovaMind") or "NovaMind"

    msg = EmailMessage()
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send_email(
    to: Iterable[str],
    subject: str,
    text: str,
    html: Optional[str] = None,
    *,
    fail_silently: bool = True,
) -> bool:
    """Send an email. Returns True on success, False on any error.

    In dev mode (SMTP_HOST unset): writes a record to
    `logs/dev-mail.log` AND logs a one-line summary to stdout. No
    network calls.

    In SMTP mode: opens a connection (with TLS if SMTP_TLS=true),
    authenticates if SMTP_USERNAME/SMTP_PASSWORD are set, and sends
    the message. Any error is caught and logged; if `fail_silently`
    is False, the exception is re-raised.
    """
    try:
        primary, to_list = _format_envelope(to)
    except ValueError as exc:
        logger.error("send_email: %s", exc)
        return False

    if not _is_configured():
        return _send_dev_stub(to_list, subject, text, html)

    return _send_smtp(to_list, subject, text, html, fail_silently=fail_silently)


def _send_dev_stub(
    to_list: list,
    subject: str,
    text: str,
    html: Optional[str],
) -> bool:
    """Write the email to a log file and stdout. Never raises."""
    log_path = _dev_log_path()
    record = (
        f"=== dev-mail @ {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n"
        f"To: {', '.join(to_list)}\n"
        f"Subject: {subject}\n"
        f"--- text/plain ---\n"
        f"{text}\n"
    )
    if html:
        record += f"--- text/html ---\n{html}\n"
    record += "=== end ===\n\n"

    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(record)
    except OSError as exc:
        # We still log to stdout so the URL is at least visible
        # in the dev's terminal during local testing.
        logger.warning("Could not write dev-mail.log (%s): %s", log_path, exc)

    # Surface the most useful field (the first URL found in the body)
    # to stdout, so a developer running `tail -F logs/dev-mail.log`
    # can grab the link without scrolling.
    url_hint = _first_url(text)
    summary = (
        f"[novamind-mailer DEV] to={to_list[0]} subject={subject!r}"
        + (f" url={url_hint}" if url_hint else "")
    )
    print(summary, flush=True)
    logger.info(summary)
    return True


def _first_url(text: str) -> Optional[str]:
    """Cheap URL extractor for the dev-stub summary line."""
    for line in text.splitlines():
        for token in line.split():
            if token.startswith(("http://", "https://")):
                # Trim trailing punctuation
                return token.rstrip(".,)")
    return None


def _send_smtp(
    to_list: list,
    subject: str,
    text: str,
    html: Optional[str],
    *,
    fail_silently: bool,
) -> bool:
    """Send via real SMTP. Returns False on any error unless re-raising."""
    host = settings.SMTP_HOST
    port = int(getattr(settings, "SMTP_PORT", 587) or 587)
    username = getattr(settings, "SMTP_USERNAME", "") or ""
    password = getattr(settings, "SMTP_PASSWORD", "") or ""
    use_tls = bool(getattr(settings, "SMTP_TLS", True))

    msg = _build_message(to_list, subject, text, html=html)

    try:
        # Port 465 is "smtps" — implicit TLS. Port 587 is "submission"
        # — STARTTLS. Port 25 is plain. The TLS flag controls STARTTLS
        # for non-465 ports; for 465 the connection is wrapped in TLS
        # before any SMTP commands run.
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as s:
                if username and password:
                    s.login(username, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                if use_tls:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                if username and password:
                    s.login(username, password)
                s.send_message(msg)
        logger.info("Sent mail to %s subject=%r via %s:%s", to_list, subject, host, port)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP send failed: %s", exc)
        if not fail_silently:
            raise
        return False
