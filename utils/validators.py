"""Валидация пользовательского ввода."""
import re
from datetime import datetime

PHONE_RE = re.compile(r"^\+?\d{9,15}$")


def validate_name(text: str) -> str | None:
    name = " ".join(text.split())
    if 2 <= len(name) <= 100:
        return name
    return None


def validate_age(text: str) -> int | None:
    if not text.strip().isdigit():
        return None
    age = int(text.strip())
    if 16 <= age <= 65:
        return age
    return None


def validate_phone(text: str) -> str | None:
    cleaned = re.sub(r"[ \-()]", "", text.strip())
    if PHONE_RE.match(cleaned):
        return cleaned if cleaned.startswith("+") else f"+{cleaned}"
    return None


def parse_interview_datetime(text: str, now: datetime) -> datetime | None:
    """Парсит 'ДД.ММ.ГГГГ ЧЧ:ММ'; дата должна быть в будущем."""
    try:
        dt = datetime.strptime(text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        return None
    if dt <= now:
        return None
    return dt
