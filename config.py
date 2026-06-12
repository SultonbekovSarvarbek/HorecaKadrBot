"""Конфигурация: .env + дефолтные пороги скрининга.

Пороги можно переопределить в БД (таблица Settings) без правки кода:
значение из Settings имеет приоритет над DEFAULT_SETTINGS.
"""
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# ── Дефолтные настройки (переопределяются в таблице Settings) ────────
DEFAULT_SETTINGS: dict[str, str] = {
    # Официант
    "waiter_age_min": "18",
    "waiter_age_max": "30",
    # Бармен (отдельный блок, по умолчанию = правила официанта)
    "bartender_age_min": "18",
    "bartender_age_max": "30",
    # Техперсонал (отдельный блок)
    "tech_age_min": "18",
    "tech_age_max": "30",
    # Повар
    "cook_age_min": "25",
    "cook_age_max": "50",
    "cook_age_max_female": "55",
    "cook_min_exp_years": "3",
    # Чаты и ссылки
    "kitchen_chat_id": "",          # chat_id чата «Кухня» (для поваров)
    "drive_link": "",               # ссылка на Google Drive с медиа для вакансий
}


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    database_url: str
    timezone: ZoneInfo


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    raw_admins = os.getenv("ADMIN_IDS", "").strip()
    parts = [p.strip() for p in raw_admins.split(",") if p.strip()]
    invalid = [p for p in parts if not p.isdigit()]
    if invalid:
        raise RuntimeError(
            f"ADMIN_IDS содержит некорректные значения: {invalid} "
            "(нужны числовые user_id через запятую)"
        )
    admin_ids = tuple(int(p) for p in parts)
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS не задан в .env (список user_id через запятую)")

    tz_name = os.getenv("TIMEZONE", "Asia/Tashkent")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as e:
        raise RuntimeError(f"Недопустимый часовой пояс в TIMEZONE: {tz_name!r}") from e

    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db"),
        timezone=tz,
    )
