"""Заглушка (maintenance mode): когда включена, бот приостановлен.

Любое действие — и со стороны клиента (кандидата), и со стороны
сотрудников/админов из БД — блокируется с сообщением «Бот приостановлен».

Единственное исключение — владелец из .env (ADMIN_IDS): он проходит, чтобы
иметь возможность выключить заглушку командой /maintenance off.

Регистрируется ПОСЛЕ DbSessionMiddleware: нужна data['session'] для чтения
флага maintenance_mode из таблицы Settings.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from config import Config
from db.repository import SettingsRepo


def _is_maintenance_cmd(message: Message) -> bool:
    """True, если сообщение — команда /maintenance (с аргументом или @botname)."""
    text = (message.text or "").strip()
    if not text.startswith("/"):
        return False
    cmd = text.split()[0].split("@", 1)[0].lower()
    return cmd == "/maintenance"


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        if session is None:
            return await handler(event, data)

        if not await SettingsRepo(session).is_maintenance():
            return await handler(event, data)

        # Заглушка включена. Владелец из .env проходит ТОЛЬКО для команды
        # /maintenance — иначе её было бы не выключить. Любое другое действие
        # блокируется даже у владельца.
        config: Config | None = data.get("config")
        user = data.get("event_from_user")
        is_owner = (
            config is not None and user is not None and user.id in config.admin_ids
        )
        if is_owner and isinstance(event, Message) and _is_maintenance_cmd(event):
            return await handler(event, data)

        # Всех остальных блокируем с уведомлением.
        if isinstance(event, Message):
            await event.answer(texts.MAINTENANCE_NOTICE)
        elif isinstance(event, CallbackQuery):
            await event.answer(texts.MAINTENANCE_NOTICE_SHORT, show_alert=True)
        return None
