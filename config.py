"""Конфигурация приложения: всё читается из .env."""
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    database_url: str
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("Asia/Tashkent"))


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
