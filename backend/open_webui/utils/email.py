"""Email delivery helpers.

Sends mail through an admin-configured SMTP server (see ``smtp.*`` config keys).
Uses only the Python standard library (``smtplib`` + ``email.message``); the
blocking send is dispatched to a worker thread so it never stalls the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from open_webui.models.config import Config

log = logging.getLogger(__name__)


async def is_email_configured() -> bool:
    """True when SMTP is enabled and has the minimum required settings."""
    values = await Config.get_many('smtp.enable', 'smtp.host', 'smtp.from_email')
    return bool(values.get('smtp.enable') and values.get('smtp.host') and values.get('smtp.from_email'))


class EmailNotConfiguredError(RuntimeError):
    """Raised when a send is attempted without a usable SMTP configuration."""


def _send_sync(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    use_ssl: bool,
    message: EmailMessage,
) -> None:
    """Blocking SMTP send — run via ``asyncio.to_thread``."""
    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            if username:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(message)


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """Send a single email. Raises ``EmailNotConfiguredError`` if SMTP is unusable.

    Any SMTP transport error propagates to the caller so endpoints can surface it.
    """
    values = await Config.get_many(
        'smtp.enable',
        'smtp.host',
        'smtp.port',
        'smtp.username',
        'smtp.password',
        'smtp.from_email',
        'smtp.from_name',
        'smtp.use_tls',
        'smtp.use_ssl',
    )

    if not (values.get('smtp.enable') and values.get('smtp.host') and values.get('smtp.from_email')):
        raise EmailNotConfiguredError('SMTP is not enabled or is missing host/from address.')

    message = EmailMessage()
    from_name = values.get('smtp.from_name') or ''
    from_email = values['smtp.from_email']
    message['From'] = formataddr((from_name, from_email)) if from_name else from_email
    message['To'] = to_email
    message['Subject'] = subject
    message.set_content(text_body or 'This email requires an HTML-capable client.')
    message.add_alternative(html_body, subtype='html')

    try:
        port = int(values.get('smtp.port') or 587)
    except (TypeError, ValueError):
        port = 587

    await asyncio.to_thread(
        _send_sync,
        host=values['smtp.host'],
        port=port,
        username=values.get('smtp.username') or '',
        password=values.get('smtp.password') or '',
        use_tls=bool(values.get('smtp.use_tls')),
        use_ssl=bool(values.get('smtp.use_ssl')),
        message=message,
    )
    log.info('Sent email to %s (subject=%r)', to_email, subject)


def _button(url: str, label: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:10px 20px;'
        f'background:#000;color:#fff;text-decoration:none;border-radius:9999px;'
        f'font-weight:600;font-size:14px">{label}</a>'
    )


def build_set_password_email(name: str, url: str, kind: str, app_name: str) -> tuple[str, str, str]:
    """Return ``(subject, html_body, text_body)`` for a set/reset-password email.

    ``kind`` is ``'setup'`` for newly created accounts or ``'reset'`` for the
    self-service forgot-password flow.
    """
    greeting = name.strip() or 'there'
    if kind == 'setup':
        subject = f'Set up your {app_name} account'
        lead = (
            f'An account has been created for you on {app_name}. '
            'Use the button below to set your password and get started.'
        )
        label = 'Set your password'
    else:
        subject = f'Reset your {app_name} password'
        lead = (
            f'We received a request to reset the password for your {app_name} account. '
            'Use the button below to choose a new password. '
            "If you didn't request this, you can safely ignore this email."
        )
        label = 'Reset your password'

    html_body = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:480px;margin:0 auto;color:#111">
  <p style="font-size:16px">Hi {greeting},</p>
  <p style="font-size:14px;line-height:1.6;color:#333">{lead}</p>
  <p style="margin:24px 0">{_button(url, label)}</p>
  <p style="font-size:12px;color:#666;line-height:1.6">
    This link expires soon and can only be used once. If the button doesn't work, copy and paste this URL into your browser:<br>
    <a href="{url}" style="color:#666;word-break:break-all">{url}</a>
  </p>
</div>"""

    text_body = f'Hi {greeting},\n\n{lead}\n\n{label}: {url}\n\nThis link expires soon and can only be used once.\n'
    return subject, html_body, text_body


def build_mfa_code_email(name: str, code: str, app_name: str) -> tuple[str, str, str]:
    """Return ``(subject, html_body, text_body)`` for a login verification code."""
    greeting = name.strip() or 'there'
    subject = f'Your {app_name} login code: {code}'
    lead = (
        f'Use this code to finish signing in to {app_name}. '
        "If you didn't try to sign in, someone may have your password — "
        'change it as soon as you can.'
    )
    html_body = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:480px;margin:0 auto;color:#111">
  <p style="font-size:16px">Hi {greeting},</p>
  <p style="font-size:14px;line-height:1.6;color:#333">{lead}</p>
  <p style="margin:24px 0;font-size:34px;font-weight:700;letter-spacing:8px;text-align:center">{code}</p>
  <p style="font-size:12px;color:#666;line-height:1.6">This code expires in 10 minutes and can only be used once.</p>
</div>"""
    text_body = (
        f'Hi {greeting},\n\n{lead}\n\nYour login code is: {code}\n\n'
        'This code expires in 10 minutes and can only be used once.\n'
    )
    return subject, html_body, text_body
