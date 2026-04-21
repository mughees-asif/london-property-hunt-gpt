from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from property_hunt.config import AppConfig


def send_smtp(config: AppConfig, *, subject: str, html: str) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    if not username or not password:
        raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD are required for smtp mode")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.email.from_address
    message["To"] = config.email.to
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)

