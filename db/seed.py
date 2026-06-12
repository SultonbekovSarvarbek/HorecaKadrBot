"""Сиды: филиалы, дефолтные настройки, админы из .env."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import Config, DEFAULT_SETTINGS
from .models import Branch, Role, Setting, User

logger = logging.getLogger("bot.seed")

BRANCHES = ["Куйлюк", "Чиланзар", "Сайрам", "Сеул Мун"]
COOK_INTERVIEW_BRANCH = "Куйлюк"  # собеседования поваров всегда здесь


async def seed_db(
    session_factory: async_sessionmaker[AsyncSession], config: Config
) -> None:
    async with session_factory() as session:
        # филиалы
        existing = set(
            (await session.scalars(select(Branch.name))).all()
        )
        for name in BRANCHES:
            if name not in existing:
                session.add(Branch(name=name))
                logger.info("Добавлен филиал: %s", name)

        # настройки по умолчанию (не перетираем существующие)
        existing_keys = set((await session.scalars(select(Setting.key))).all())
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing_keys:
                session.add(Setting(key=key, value=value))

        # админы из .env попадают в whitelist автоматически
        existing_tg = set((await session.scalars(select(User.tg_id))).all())
        for tg_id in config.admin_ids:
            if tg_id not in existing_tg:
                session.add(User(tg_id=tg_id, role=Role.ADMIN, name="admin (.env)"))
                logger.info("Добавлен админ из .env: %s", tg_id)

        await session.commit()


async def get_cook_interview_branch(session: AsyncSession) -> Branch | None:
    return await session.scalar(
        select(Branch).where(Branch.name == COOK_INTERVIEW_BRANCH)
    )
