"""Сбор и форматирование аналитики для админ-панели."""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import FUNNEL_ORDER, Vacancy
from db.repository import AnalyticsRepository, period_start


async def build_analytics_text(session: AsyncSession, now: datetime) -> str:
    repo = AnalyticsRepository(session)

    today = await repo.count_since(period_start(0, now))
    week = await repo.count_since(period_start(7, now))
    month = await repo.count_since(period_start(30, now))
    total = await repo.count_since(None)

    by_vacancy = await repo.counts_by_vacancy()
    vacancy_lines = "\n".join(
        f"• {texts.VACANCY_LABELS[v]}: {by_vacancy.get(v, 0)}" for v in Vacancy
    )

    # Конверсия: % от всех заявок, достигших каждого этапа воронки
    reach = await repo.funnel_reach_counts()
    funnel_lines = []
    for status in FUNNEL_ORDER:
        count = reach.get(status, 0)
        pct = (count / total * 100) if total else 0
        funnel_lines.append(
            f"• {texts.STATUS_LABELS[status]}: {count} ({pct:.0f}%)"
        )

    by_source = await repo.counts_by_source()
    source_lines = "\n".join(
        f"• {source}: {count}"
        for source, count in sorted(by_source.items(), key=lambda x: -x[1])
    ) or "• —"

    return texts.ANALYTICS_TEMPLATE.format(
        today=today,
        week=week,
        month=month,
        total=total,
        by_vacancy=vacancy_lines + "\n",
        funnel="\n".join(funnel_lines) + "\n",
        by_source=source_lines,
    )
