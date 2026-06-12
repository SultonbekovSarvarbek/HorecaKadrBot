"""Напоминания о собеседованиях через APScheduler (за 3 часа до начала)."""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import texts
from db.repository import InterviewRepository

logger = logging.getLogger("bot.scheduler")

REMIND_BEFORE = timedelta(hours=3)


async def send_interview_reminder(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    interview_id: int,
) -> None:
    async with session_factory() as session:
        repo = InterviewRepository(session)
        interview = await repo.get_by_id(interview_id)
        if interview is None or interview.reminded:
            return
        candidate = await interview.awaitable_attrs.candidate
        try:
            await bot.send_message(
                candidate.tg_id,
                texts.INTERVIEW_REMINDER.format(dt=f"{interview.datetime:%H:%M}"),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Не удалось отправить напоминание кандидату %s: %s", candidate.tg_id, e
            )
        await repo.mark_reminded(interview_id)


def schedule_reminder(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    interview_id: int,
    interview_dt: datetime,
) -> None:
    """Ставит задачу-напоминание за 3 часа до собеседования.

    Если до собеседования меньше 3 часов — напоминание уйдёт почти сразу.
    """
    run_at = interview_dt - REMIND_BEFORE
    now = datetime.now()
    if run_at <= now:
        run_at = now + timedelta(seconds=10)
    scheduler.add_job(
        send_interview_reminder,
        trigger="date",
        run_date=run_at,
        args=[bot, session_factory, interview_id],
        id=f"interview_reminder_{interview_id}",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "Напоминание по собеседованию #%s запланировано на %s", interview_id, run_at
    )


async def restore_pending_reminders(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """После рестарта бота восстанавливает напоминания из БД."""
    async with session_factory() as session:
        repo = InterviewRepository(session)
        pending = await repo.get_pending_reminders(datetime.now())
    for interview in pending:
        schedule_reminder(scheduler, bot, session_factory, interview.id, interview.datetime)
    if pending:
        logger.info("Восстановлено напоминаний: %d", len(pending))
