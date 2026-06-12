"""Уведомления админам о новых заявках."""
import logging

from aiogram import Bot

import texts
from db.models import Candidate
from keyboards.admin import new_application_kb
from utils.formatting import candidate_card

logger = logging.getLogger("bot.notifications")


async def notify_admins_new_application(
    bot: Bot, admin_ids: tuple[int, ...], candidate: Candidate
) -> None:
    text = texts.NEW_APPLICATION_TITLE + candidate_card(candidate)
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id, text, reply_markup=new_application_kb(candidate.id)
            )
        except Exception as e:  # noqa: BLE001 — один недоступный админ не должен ломать рассылку
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, e)
