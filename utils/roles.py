"""Фильтр доступа по ролям (whitelist в таблице Users)."""
from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Role
from db.repository import UserRepo


class RoleFilter(BaseFilter):
    """Пропускает только сотрудников с указанными ролями.

    В хендлер дополнительно прокидывает staff_user (модель User).
    """

    def __init__(self, *roles: Role):
        self.roles = roles

    async def __call__(self, event: TelegramObject, session: AsyncSession):
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:
            return False
        db_user = await UserRepo(session).by_tg(tg_user.id)
        if db_user is not None and db_user.role in self.roles:
            return {"staff_user": db_user}
        return False
