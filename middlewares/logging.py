"""Логирование входящих апдейтов."""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger("bot.updates")


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            logger.info(
                "message from=%s text=%r",
                event.from_user.id if event.from_user else "?",
                (event.text or event.content_type)[:100],
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                "callback from=%s data=%r",
                event.from_user.id,
                event.data,
            )
        return await handler(event, data)
