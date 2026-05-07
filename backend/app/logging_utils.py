import logging
import re


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
PASSWORD_RE = re.compile(
    r"(?i)\b(пароль|password|pwd|pass)\b\s*[:=]?\s*\S+"
)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def sanitize_for_log(value: str) -> str:
    sanitized = EMAIL_RE.sub("[email]", value)
    sanitized = PHONE_RE.sub("[phone]", sanitized)
    sanitized = PASSWORD_RE.sub(r"\1 [redacted]", sanitized)
    if len(sanitized) > 160:
        return sanitized[:157] + "..."
    return sanitized
