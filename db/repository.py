"""Репозиторий: все операции с БД в одном месте."""
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Candidate,
    CandidateStatus,
    Interview,
    StatusLog,
    TERMINAL_STATUSES,
    Vacancy,
)


class CandidateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_application(self, tg_id: int) -> Candidate | None:
        """Последняя заявка пользователя в НЕтерминальном статусе."""
        stmt = (
            select(Candidate)
            .where(
                Candidate.tg_id == tg_id,
                Candidate.status.not_in(TERMINAL_STATUSES),
            )
            .order_by(Candidate.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def create_candidate(self, **kwargs) -> Candidate:
        candidate = Candidate(**kwargs)
        self.session.add(candidate)
        await self.session.flush()
        # фиксируем стартовый статус в логе для аналитики воронки
        self.session.add(
            StatusLog(
                candidate_id=candidate.id,
                old_status=None,
                new_status=candidate.status,
            )
        )
        await self.session.commit()
        return candidate

    async def get_by_id(self, candidate_id: int) -> Candidate | None:
        return await self.session.get(Candidate, candidate_id)

    async def change_status(
        self, candidate: Candidate, new_status: CandidateStatus
    ) -> None:
        old = candidate.status
        if old == new_status:
            return
        candidate.status = new_status
        self.session.add(
            StatusLog(candidate_id=candidate.id, old_status=old, new_status=new_status)
        )
        await self.session.commit()

    async def list_filtered(
        self,
        vacancy: Vacancy | None,
        status: CandidateStatus | None,
        page: int,
        per_page: int = 5,
    ) -> tuple[list[Candidate], int]:
        """Страница кандидатов + общее количество под фильтром."""
        conditions = []
        if vacancy is not None:
            conditions.append(Candidate.vacancy == vacancy)
        if status is not None:
            conditions.append(Candidate.status == status)

        total = await self.session.scalar(
            select(func.count(Candidate.id)).where(*conditions)
        )
        stmt = (
            select(Candidate)
            .where(*conditions)
            .order_by(Candidate.created_at.desc())
            .offset(page * per_page)
            .limit(per_page)
        )
        rows = (await self.session.scalars(stmt)).all()
        return list(rows), total or 0

    async def list_all(self) -> list[Candidate]:
        stmt = select(Candidate).order_by(Candidate.created_at.desc())
        return list((await self.session.scalars(stmt)).all())


class InterviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, candidate_id: int, dt: datetime) -> Interview:
        interview = Interview(candidate_id=candidate_id, datetime=dt, reminded=False)
        self.session.add(interview)
        await self.session.commit()
        return interview

    async def get_pending_reminders(self, now: datetime) -> list[Interview]:
        """Будущие собеседования, по которым ещё не отправлено напоминание."""
        stmt = select(Interview).where(
            Interview.reminded.is_(False),
            Interview.datetime > now,
        )
        return list((await self.session.scalars(stmt)).all())

    async def mark_reminded(self, interview_id: int) -> None:
        await self.session.execute(
            update(Interview).where(Interview.id == interview_id).values(reminded=True)
        )
        await self.session.commit()

    async def get_by_id(self, interview_id: int) -> Interview | None:
        return await self.session.get(Interview, interview_id)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def count_since(self, since: datetime | None) -> int:
        stmt = select(func.count(Candidate.id))
        if since is not None:
            stmt = stmt.where(Candidate.created_at >= since)
        return await self.session.scalar(stmt) or 0

    async def counts_by_vacancy(self) -> dict[Vacancy, int]:
        stmt = select(Candidate.vacancy, func.count(Candidate.id)).group_by(
            Candidate.vacancy
        )
        rows = (await self.session.execute(stmt)).all()
        return {vacancy: count for vacancy, count in rows}

    async def counts_by_source(self) -> dict[str, int]:
        stmt = select(
            func.coalesce(Candidate.source, "—"), func.count(Candidate.id)
        ).group_by(Candidate.source)
        rows = (await self.session.execute(stmt)).all()
        return {source: count for source, count in rows}

    async def funnel_reach_counts(self) -> dict[CandidateStatus, int]:
        """Сколько уникальных кандидатов когда-либо достигало каждого статуса."""
        stmt = select(
            StatusLog.new_status, func.count(func.distinct(StatusLog.candidate_id))
        ).group_by(StatusLog.new_status)
        rows = (await self.session.execute(stmt)).all()
        return {status: count for status, count in rows}


def period_start(days: int, now: datetime) -> datetime:
    """Начало периода: days=0 — сегодня с 00:00, иначе now - days."""
    if days == 0:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=days)
