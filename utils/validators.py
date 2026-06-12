"""Валидация пользовательского ввода."""
import re
from datetime import datetime

PHONE_RE = re.compile(r"^\+?\d{9,15}$")


def validate_name(text: str) -> str | None:
    name = " ".join(text.split())
    if 2 <= len(name) <= 150:
        return name
    return None


def validate_age(text: str) -> int | None:
    if not text.strip().isdigit():
        return None
    age = int(text.strip())
    return age if 14 <= age <= 80 else None


def validate_int(text: str, lo: int, hi: int) -> int | None:
    if not text.strip().isdigit():
        return None
    value = int(text.strip())
    return value if lo <= value <= hi else None


def validate_phone(text: str) -> str | None:
    cleaned = re.sub(r"[ \-()]", "", text.strip())
    if PHONE_RE.match(cleaned):
        return cleaned if cleaned.startswith("+") else f"+{cleaned}"
    return None


def parse_date(text: str) -> datetime | None:
    """'ДД.ММ.ГГГГ' → datetime (00:00)."""
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y")
    except ValueError:
        return None


def parse_index(data: str, options_len: int) -> int | None:
    """Безопасно достаёт индекс из callback 'prefix:N'."""
    try:
        idx = int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        return None
    return idx if 0 <= idx < options_len else None
