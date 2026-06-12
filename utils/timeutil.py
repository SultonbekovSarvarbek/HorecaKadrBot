"""Единое «текущее время» проекта в часовом поясе из TIMEZONE.

Сервер может работать в UTC — поэтому везде (БД, напоминания, аналитика,
парсинг даты собеседования) используется наивное время в зоне бизнеса.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))


def now_local() -> datetime:
    """Наивный datetime в бизнес-зоне (тот же вид, что вводит HR)."""
    return datetime.now(TZ).replace(tzinfo=None)
