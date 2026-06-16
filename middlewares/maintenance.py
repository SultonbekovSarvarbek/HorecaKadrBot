"""Заглушка (maintenance mode): когда включена, бот приостановлен для ВСЕХ.

Управляется только с сервера через .env (MAINTENANCE_MODE=1) — в самом боте
команды нет. Любое действие — и со стороны клиента (кандидата), и со стороны
сотрудников/админов, и со стороны владельца — блокируется с сообщением
«Бот приостановлен».

Чтобы включить/выключить: поменять MAINTENANCE_MODE в .env и перезапустить бота.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import texts
from config import Config


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        config: Config | None = data.get("config")
        if config is None or not config.maintenance:
            return await handler(event, data)

        # Заглушка включена — блокируем всех без исключений.
        if isinstance(event, Message):
            await event.answer(texts.MAINTENANCE_NOTICE)
        elif isinstance(event, CallbackQuery):
            await event.answer(texts.MAINTENANCE_NOTICE_SHORT, show_alert=True)
        return None
