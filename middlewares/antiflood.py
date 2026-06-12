"""Антифлуд: не чаще одного апдейта в 0.5 сек от пользователя."""
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            last = self._last_seen.get(user.id, 0.0)
            if now - last < self.rate_limit:
                return None  # молча игнорируем флуд
            self._last_seen[user.id] = now
            # периодическая чистка, чтобы словарь не рос бесконечно
            if len(self._last_seen) > 10_000:
                cutoff = now - 60
                self._last_seen = {
                    uid: ts for uid, ts in self._last_seen.items() if ts > cutoff
                }
        return await handler(event, data)
