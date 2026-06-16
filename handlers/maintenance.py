"""Управление заглушкой (maintenance mode) — только для владельца из .env.

Команда доступна владельцу даже когда бот приостановлен (MaintenanceMiddleware
пропускает ADMIN_IDS из .env), поэтому именно ею заглушка и выключается.

    /maintenance on    — приостановить бота (заглушка для всех)
    /maintenance off   — возобновить работу
    /maintenance       — показать текущий статус
"""
import logging

from aiogram import Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from config import Config
from db.repository import AuditRepo, SettingsRepo

logger = logging.getLogger("bot.maintenance")
router = Router(name="maintenance")


class OwnerFilter(BaseFilter):
    """Пропускает только владельцев из .env (ADMIN_IDS)."""

    async def __call__(self, event: TelegramObject, config: Config) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in config.admin_ids


router.message.filter(OwnerFilter())


@router.message(Command("maintenance"))
async def cmd_maintenance(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    repo = SettingsRepo(session)
    arg = (command.args or "").strip().lower()

    if arg in ("on", "вкл", "1"):
        await repo.set_maintenance(True)
        await AuditRepo(session).log(
            message.from_user.id, "owner", "maintenance", "on"
        )
        await message.answer(texts.MAINTENANCE_ENABLED)
    elif arg in ("off", "выкл", "0"):
        await repo.set_maintenance(False)
        await AuditRepo(session).log(
            message.from_user.id, "owner", "maintenance", "off"
        )
        await message.answer(texts.MAINTENANCE_DISABLED)
    else:
        on = await repo.is_maintenance()
        await message.answer(
            texts.MAINTENANCE_STATUS_ON if on else texts.MAINTENANCE_STATUS_OFF
        )
