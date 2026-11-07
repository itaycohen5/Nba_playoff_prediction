"""Gmail SMTP delivery. Credentials and links are never logged."""
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlsplit


class DeliveryError(Exception):
    pass


def normalize_email(value):
    value = value.strip().lower()
    if (len(value) > 254 or not value.isascii() or
            not re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", value)):
        raise ValueError('יש להזין כתובת מייל תקינה')
    local, domain = value.rsplit('@', 1)
    if len(local) > 64 or local.startswith('.') or local.endswith('.') or '..' in value or any(not part or part.startswith('-') or part.endswith('-') for part in domain.split('.')):
        raise ValueError('יש להזין כתובת מייל תקינה')
    return value


def settings():
    sender = os.getenv('GMAIL_USER', '').strip()
    password = os.getenv('GMAIL_APP_PASSWORD', '').replace(' ', '')
    origin = os.getenv('PUBLIC_APP_URL', '').strip().rstrip('/')
    parsed = urlsplit(origin)
    local = parsed.hostname in ('localhost', '127.0.0.1') and not os.getenv('VERCEL')
    if (not sender or not password or not parsed.hostname or parsed.username or parsed.password or
            parsed.query or parsed.fragment or parsed.path or (parsed.scheme != 'https' and not (local and parsed.scheme == 'http'))):
        raise DeliveryError('Email delivery is not configured')
    try:
        normalize_email(sender)
    except ValueError:
        raise DeliveryError('Email delivery is not configured') from None
    return sender, password, origin


def is_configured():
    try:
        settings()
        return True
    except DeliveryError:
        return False


def send_link(recipient, code, purpose):
    sender, password, origin = settings()
    if purpose not in ('verify-email', 'reset-password'):
        raise ValueError('Unsupported email purpose')
    link = f'{origin}/{purpose}#token={code}'
    verify = purpose == 'verify-email'
    action = 'אימות כתובת המייל' if verify else 'איפוס הסיסמה'
    message = EmailMessage()
    message['From'] = formataddr(('Playoff Lab', sender))
    message['To'] = normalize_email(recipient)
    message['Subject'] = f'Playoff Lab — {action}'
    message.set_content(f'{action}\n\nלפתיחת העמוד:\n{link}\n\nהקישור תקף ל־30 דקות ולשימוש אחד.\nאם לא ביקשת את הפעולה, אפשר להתעלם מההודעה.\n\nPlayoff Lab')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10, context=ssl.create_default_context()) as smtp:
            smtp.login(sender, password)
            refused = smtp.send_message(message)
            if refused:
                raise DeliveryError('Email was not accepted')
    except (OSError, smtplib.SMTPException):
        raise DeliveryError('Email delivery failed') from None
