"""Еженедельная сверка: каждый понедельник 10:00 — чеклист рекрутерам."""
import logging
from datetime import timedelta
from html import escape

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import texts
from db.models import CandidateStatus
from db.repository import ReportRepo, VacancyRepo
from services.notify import notify_recruiters
from utils.timeutil import now_local

logger = logging.getLogger("bot.scheduler")


async def build_weekly_checkin(session: AsyncSession) -> str:
    now = now_local()
    week_ago = now - timedelta(days=7)
    parts = [texts.WEEKLY_CHECKIN_TITLE]

    vac_repo = VacancyRepo(session)
    vacancies = await vac_repo.open_vacancies()
    if vacancies:
        hired = await vac_repo.hired_counts([v.id for v in vacancies])
        lines = "\n".join(
            f"• #{v.id} {texts.POSITION_LABELS[v.position]} · {escape(v.branch.name)} "
            f"({hired.get(v.id, 0)}/{v.quota})"
            for v in vacancies
        )
        parts.append(texts.WEEKLY_VACANCIES.format(lines=lines))
    else:
        parts.append(texts.WEEKLY_NO_VACANCIES)

    report = ReportRepo(session)
    hired_week = await report.status_changed_between(CandidateStatus.HIRED, week_ago, now)
    if hired_week:
        lines = "\n".join(
            f"• #{c.id} {escape(c.full_name)} — {texts.POSITION_LABELS[c.vacancy.position]} "
            f"({escape(c.vacancy.branch.name)})"
            for c in hired_week
        )
        parts.append(texts.WEEKLY_HIRED.format(lines=lines))
    else:
        parts.append(texts.WEEKLY_NO_HIRED)

    failed = await report.status_changed_between(
        CandidateStatus.INTERNSHIP_FAILED, week_ago, now
    )
    if failed:
        lines = "\n".join(
            f"• #{c.id} {escape(c.full_name)}"
            + (f" — {escape(c.status_reason)}" if c.status_reason else "")
            for c in failed
        )
        parts.append(texts.WEEKLY_INTERNSHIP_FAILED.format(lines=lines))

    rejections = await report.rejection_reasons_between(week_ago, now)
    lines = "\n".join(
        f"• {texts.REJECTION_LABELS[r]}: {cnt}"
        for r, cnt in sorted(rejections.items(), key=lambda x: -x[1])
    ) or "• —"
    parts.append(texts.WEEKLY_REJECTIONS.format(lines=lines))

    return "".join(parts)


async def send_weekly_checkin(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as session:
        text = await build_weekly_checkin(session)
        await notify_recruiters(bot, session, text)
    logger.info("Еженедельная сверка отправлена рекрутерам")


def setup_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    scheduler.add_job(
        send_weekly_checkin,
        trigger="cron",
        day_of_week="mon",
        hour=10,
        minute=0,
        args=[bot, session_factory],
        id="weekly_checkin",
        replace_existing=True,
        misfire_grace_time=3600,
    )
