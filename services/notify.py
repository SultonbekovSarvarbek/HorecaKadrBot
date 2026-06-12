"""Рассылка карточек и уведомлений в служебные чаты и сотрудникам."""
import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import Candidate, Position, Role
from db.repository import SettingsRepo, UserRepo
from .cards import candidate_card

logger = logging.getLogger("bot.notify")


async def _safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except Exception as e:  # noqa: BLE001 — недоступный чат не должен ломать поток
        logger.warning("Не доставлено в чат %s: %s", chat_id, e)
        return False


async def send_invited_card(bot: Bot, session: AsyncSession, c: Candidate) -> None:
    """Карточка «Приглашён»: в чат филиала (повара — в чат «Кухня») + рекрутерам."""
    text = texts.CARD_NEW_CANDIDATE + candidate_card(c)

    if c.vacancy.position == Position.COOK:
        kitchen_chat = await SettingsRepo(session).get("kitchen_chat_id")
        if kitchen_chat.lstrip("-").isdigit():
            await _safe_send(bot, int(kitchen_chat), text)
        else:
            logger.warning("kitchen_chat_id не настроен — карточка повара только рекрутерам")
        # плюс лично шеф-повару
        for chef in await UserRepo(session).by_role(Role.CHEF):
            await _safe_send(bot, chef.tg_id, text)
    else:
        if c.vacancy.branch.chat_id:
            await _safe_send(bot, c.vacancy.branch.chat_id, text)
        else:
            logger.warning(
                "У филиала «%s» нет chat_id — карточка только рекрутерам",
                c.vacancy.branch.name,
            )

    await notify_recruiters(bot, session, text)


async def notify_recruiters(bot: Bot, session: AsyncSession, text: str, **kwargs) -> None:
    for user in await UserRepo(session).by_role(Role.RECRUITER, Role.ADMIN):
        await _safe_send(bot, user.tg_id, text, **kwargs)
