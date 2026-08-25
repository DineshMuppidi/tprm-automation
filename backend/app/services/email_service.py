"""Vendor communication (Phase 1 §7: assignment + completion notices).

Reminder emails (7/3/1 days before deadline) and deadline-escalation emails
are the same `send()` primitive but are triggered on a schedule — that
scheduling is Airflow's job and lands in Phase 2. This module only sends
the two notifications that are triggered synchronously by an action inside
Phase 1 itself: assignment and completion.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage
from smtplib import SMTP

from app.config import get_settings

logger = logging.getLogger("tprm.email")


@dataclass
class Email:
    to: str
    subject: str
    body: str


class EmailProvider(ABC):
    @abstractmethod
    def send(self, email: Email) -> None: ...


class ConsoleEmailProvider(EmailProvider):
    """Default provider: logs the email instead of sending it, so the
    platform runs end-to-end with zero mail infrastructure configured."""

    def send(self, email: Email) -> None:
        logger.info(
            "=== EMAIL (console provider) ===\nTo: %s\nSubject: %s\n\n%s\n=================================",
            email.to, email.subject, email.body,
        )


class SMTPEmailProvider(EmailProvider):
    def __init__(self, host: str, port: int, user: str, password: str, from_addr: str):
        self.host, self.port, self.user, self.password, self.from_addr = host, port, user, password, from_addr

    def send(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.body)
        with SMTP(self.host, self.port) as server:
            server.starttls()
            if self.user:
                server.login(self.user, self.password)
            server.send_message(msg)


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.email_provider == "smtp":
        return SMTPEmailProvider(
            settings.smtp_host, settings.smtp_port, settings.smtp_user,
            settings.smtp_password, settings.email_from,
        )
    return ConsoleEmailProvider()


def send_assignment_email(to: str, vendor_name: str, magic_link_url: str, due_at_str: str) -> None:
    body = (
        f"Hello,\n\n{vendor_name} has been asked to complete a third-party risk "
        f"assessment.\n\nStart here (link expires in 15 minutes, request a new "
        f"one anytime): {magic_link_url}\n\nDue: {due_at_str}\n\n"
        f"You can save your progress and return at any time before the deadline.\n\n"
        f"— TPRM Automation Platform"
    )
    get_email_provider().send(Email(to=to, subject=f"Security Assessment Requested — {vendor_name}", body=body))


def send_completion_email(to: str, vendor_name: str, overall_score: float) -> None:
    body = (
        f"Hello,\n\nThank you for completing the security assessment for "
        f"{vendor_name}.\n\nYour compliance strength score: {overall_score:.0f}/100.\n\n"
        f"Your assessment report and any follow-up items will be shared by your "
        f"risk owner shortly.\n\n— TPRM Automation Platform"
    )
    get_email_provider().send(Email(to=to, subject=f"Assessment Complete — {vendor_name}", body=body))
