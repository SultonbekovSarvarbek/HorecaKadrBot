"""Репозитории: вся работа с БД в одном месте."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import DEFAULT_SETTINGS
from .models import (
    AuditLog,
    Branch,
    Candidate,
    CandidateStatus,
    Position,
    RejectionReason,
    Role,
    Setting,
    StaffRequest,
    StaffRequestStatus,
    StatusLog,
    TERMINAL_STATUSES,
    User,
    Vacancy,
    VacancyStatus,
)


class SettingsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> str:
        setting = await self.session.get(Setting, key)
        if setting is not None and setting.value != "":
            return setting.value
        return DEFAULT_SETTINGS.get(key, "")

    async def get_int(self, key: str, default: int = 0) -> int:
        raw = await self.get(key)
        try:
            return int(raw)
        except ValueError:
            return default

    async def set(self, key: str, value: str) -> None:
        setting = await self.session.get(Setting, key)
        if setting is None:
            self.session.add(Setting(key=key, value=value))
        else:
            setting.value = value
        await self.session.commit()

    async def all(self) -> dict[str, str]:
        rows = (await self.session.scalars(select(Setting))).all()
        merged = dict(DEFAULT_SETTINGS)
        merged.update({s.key: s.value for s in rows if s.value != ""})
        return merged


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_tg(self, tg_id: int) -> User | None:
        return await self.session.scalar(
            select(User).where(User.tg_id == tg_id).options(selectinload(User.branch))
        )

    async def by_role(self, *roles: Role) -> list[User]:
        stmt = select(User).where(User.role.in_(roles))
        return list((await self.session.scalars(stmt)).all())

    async def add(
        self, tg_id: int, role: Role, name: str = "", branch_id: int | None = None
    ) -> User:
        user = User(tg_id=tg_id, role=role, name=name, branch_id=branch_id)
        self.session.add(user)
        await self.session.commit()
        return user

    async def all(self) -> list[User]:
        stmt = select(User).options(selectinload(User.branch)).order_by(User.role)
        return list((await self.session.scalars(stmt)).all())


class BranchRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def all(self) -> list[Branch]:
        return list((await self.session.scalars(select(Branch).order_by(Branch.id))).all())

    async def by_id(self, branch_id: int) -> Branch | None:
        return await self.session.get(Branch, branch_id)

    async def by_name(self, name: str) -> Branch | None:
        return await self.session.scalar(
            select(Branch).where(func.lower(Branch.name) == name.lower().strip())
        )

    async def set_chat(self, branch_id: int, chat_id: int) -> None:
        branch = await self.session.get(Branch, branch_id)
        if branch:
            branch.chat_id = chat_id
            await self.session.commit()


class VacancyRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_id(self, vacancy_id: int) -> Vacancy | None:
        return await self.session.scalar(
            select(Vacancy)
            .where(Vacancy.id == vacancy_id)
            .options(selectinload(Vacancy.branch))
        )

    async def open_vacancies(self, branch_id: int | None = None) -> list[Vacancy]:
        stmt = (
            select(Vacancy)
            .where(Vacancy.status == VacancyStatus.OPEN)
            .options(selectinload(Vacancy.branch))
            .order_by(Vacancy.id)
        )
        if branch_id is not None:
            stmt = stmt.where(Vacancy.branch_id == branch_id)
        return list((await self.session.scalars(stmt)).all())

    async def all_vacancies(self) -> list[Vacancy]:
        stmt = select(Vacancy).options(selectinload(Vacancy.branch)).order_by(Vacancy.id)
        return list((await self.session.scalars(stmt)).all())

    async def create(self, **kwargs) -> Vacancy:
        vacancy = Vacancy(**kwargs)
        self.session.add(vacancy)
        await self.session.commit()
        return await self.by_id(vacancy.id)

    async def close(self, vacancy_id: int) -> Vacancy | None:
        vacancy = await self.by_id(vacancy_id)
        if vacancy:
            vacancy.status = VacancyStatus.CLOSED
            await self.session.commit()
        return vacancy

    async def set_quota(self, vacancy_id: int, quota: int) -> Vacancy | None:
        vacancy = await self.by_id(vacancy_id)
        if vacancy:
            vacancy.quota = quota
            await self.session.commit()
        return vacancy

    async def hired_count(self, vacancy_id: int) -> int:
        return (
            await self.session.scalar(
                select(func.count(Candidate.id)).where(
                    Candidate.vacancy_id == vacancy_id,
                    Candidate.status == CandidateStatus.HIRED,
                )
            )
            or 0
        )

    async def hired_counts(self, vacancy_ids: list[int]) -> dict[int, int]:
        if not vacancy_ids:
            return {}
        stmt = (
            select(Candidate.vacancy_id, func.count(Candidate.id))
            .where(
                Candidate.vacancy_id.in_(vacancy_ids),
                Candidate.status == CandidateStatus.HIRED,
            )
            .group_by(Candidate.vacancy_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {vid: cnt for vid, cnt in rows}


class CandidateRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_id(self, candidate_id: int) -> Candidate | None:
        return await self.session.scalar(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(selectinload(Candidate.vacancy).selectinload(Vacancy.branch))
        )

    async def active_application(self, tg_id: int) -> Candidate | None:
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

    async def create(self, **kwargs) -> Candidate:
        candidate = Candidate(**kwargs)
        self.session.add(candidate)
        await self.session.flush()
        self.session.add(
            StatusLog(
                candidate_id=candidate.id,
                old_status=None,
                new_status=candidate.status,
            )
        )
        await self.session.commit()
        return await self.by_id(candidate.id)

    async def change_status(
        self,
        candidate: Candidate,
        new_status: CandidateStatus,
        changed_by_tg: int | None = None,
        reason: str | None = None,
    ) -> None:
        old = candidate.status
        if old == new_status:
            return
        candidate.status = new_status
        if reason:
            candidate.status_reason = reason
        self.session.add(
            StatusLog(
                candidate_id=candidate.id,
                old_status=old,
                new_status=new_status,
                changed_by_tg=changed_by_tg,
            )
        )
        await self.session.commit()

    async def list_filtered(
        self,
        branch_id: int | None = None,
        position: Position | None = None,
        status: CandidateStatus | None = None,
        statuses: list[CandidateStatus] | None = None,
        page: int = 0,
        per_page: int = 5,
    ) -> tuple[list[Candidate], int]:
        conditions = []
        if branch_id is not None or position is not None:
            stmt_base = select(Candidate).join(Vacancy, Candidate.vacancy_id == Vacancy.id)
            count_base = select(func.count(Candidate.id)).join(
                Vacancy, Candidate.vacancy_id == Vacancy.id
            )
            if branch_id is not None:
                conditions.append(Vacancy.branch_id == branch_id)
            if position is not None:
                conditions.append(Vacancy.position == position)
        else:
            stmt_base = select(Candidate)
            count_base = select(func.count(Candidate.id))
        if status is not None:
            conditions.append(Candidate.status == status)
        if statuses is not None:
            conditions.append(Candidate.status.in_(statuses))

        total = await self.session.scalar(count_base.where(*conditions)) or 0
        stmt = (
            stmt_base.where(*conditions)
            .options(selectinload(Candidate.vacancy).selectinload(Vacancy.branch))
            .order_by(Candidate.created_at.desc())
            .offset(page * per_page)
            .limit(per_page)
        )
        rows = (await self.session.scalars(stmt)).all()
        return list(rows), total

    async def cooks_all_branches(
        self, page: int = 0, per_page: int = 5
    ) -> tuple[list[Candidate], int]:
        return await self.list_filtered(
            position=Position.COOK,
            statuses=[
                s for s in CandidateStatus
                if s not in (CandidateStatus.NEW, CandidateStatus.SCREEN_REJECTED)
            ],
            page=page,
            per_page=per_page,
        )


class StaffRequestRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> StaffRequest:
        req = StaffRequest(**kwargs)
        self.session.add(req)
        await self.session.commit()
        return req

    async def by_id(self, request_id: int) -> StaffRequest | None:
        return await self.session.scalar(
            select(StaffRequest)
            .where(StaffRequest.id == request_id)
            .options(selectinload(StaffRequest.branch))
        )

    async def set_status(self, req: StaffRequest, status: StaffRequestStatus) -> None:
        req.status = status
        await self.session.commit()


class AuditRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self, user_tg_id: int, role: str, action: str, details: str = ""
    ) -> None:
        self.session.add(
            AuditLog(user_tg_id=user_tg_id, role=role, action=action, details=details)
        )
        await self.session.commit()


class ReportRepo:
    """Агрегаты для /report и еженедельной сверки."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _candidate_ids(
        self,
        date_from: datetime,
        date_to: datetime,
        branch_id: int | None,
        position: Position | None,
    ) -> list[int]:
        stmt = select(Candidate.id).where(
            Candidate.created_at >= date_from, Candidate.created_at < date_to
        )
        if branch_id is not None or position is not None:
            stmt = stmt.join(Vacancy, Candidate.vacancy_id == Vacancy.id)
            if branch_id is not None:
                stmt = stmt.where(Vacancy.branch_id == branch_id)
            if position is not None:
                stmt = stmt.where(Vacancy.position == position)
        return list((await self.session.scalars(stmt)).all())

    async def funnel(
        self,
        date_from: datetime,
        date_to: datetime,
        branch_id: int | None = None,
        position: Position | None = None,
    ) -> dict:
        ids = await self._candidate_ids(date_from, date_to, branch_id, position)
        if not ids:
            return {
                "applied": 0, "screened": 0, "came": 0, "internship": 0, "hired": 0,
                "rejections": {}, "sources": {}, "candidate_ids": [],
            }

        # достигнутые этапы — по StatusLog
        stmt = (
            select(StatusLog.new_status, func.count(func.distinct(StatusLog.candidate_id)))
            .where(StatusLog.candidate_id.in_(ids))
            .group_by(StatusLog.new_status)
        )
        reach = {st: cnt for st, cnt in (await self.session.execute(stmt)).all()}

        rej_stmt = (
            select(Candidate.rejection_reason, func.count(Candidate.id))
            .where(
                Candidate.id.in_(ids),
                Candidate.status == CandidateStatus.SCREEN_REJECTED,
            )
            .group_by(Candidate.rejection_reason)
        )
        rejections = {
            reason: cnt
            for reason, cnt in (await self.session.execute(rej_stmt)).all()
            if reason is not None
        }

        src_stmt = (
            select(func.coalesce(Candidate.source, "—"), func.count(Candidate.id))
            .where(Candidate.id.in_(ids))
            .group_by(Candidate.source)
        )
        sources = {src: cnt for src, cnt in (await self.session.execute(src_stmt)).all()}

        return {
            "applied": len(ids),
            "screened": reach.get(CandidateStatus.INVITED, 0),
            "came": reach.get(CandidateStatus.CAME, 0),
            "internship": reach.get(CandidateStatus.INTERNSHIP, 0),
            "hired": reach.get(CandidateStatus.HIRED, 0),
            "rejections": rejections,
            "sources": sources,
            "candidate_ids": ids,
        }

    async def candidates_full(
        self,
        date_from: datetime,
        date_to: datetime,
        branch_id: int | None = None,
        position: Position | None = None,
    ) -> list[Candidate]:
        """ВСЕ анкеты периода (включая отказы по критериям) для Excel."""
        ids = await self._candidate_ids(date_from, date_to, branch_id, position)
        if not ids:
            return []
        stmt = (
            select(Candidate)
            .where(Candidate.id.in_(ids))
            .options(selectinload(Candidate.vacancy).selectinload(Vacancy.branch))
            .order_by(Candidate.created_at)
        )
        return list((await self.session.scalars(stmt)).all())

    async def status_changed_between(
        self, status: CandidateStatus, date_from: datetime, date_to: datetime
    ) -> list[Candidate]:
        """Кандидаты, получившие статус в интервале (для еженедельной сверки)."""
        stmt = (
            select(Candidate)
            .join(StatusLog, StatusLog.candidate_id == Candidate.id)
            .where(
                StatusLog.new_status == status,
                StatusLog.changed_at >= date_from,
                StatusLog.changed_at < date_to,
            )
            .options(selectinload(Candidate.vacancy).selectinload(Vacancy.branch))
            .distinct()
        )
        return list((await self.session.scalars(stmt)).all())

    async def rejection_reasons_between(
        self, date_from: datetime, date_to: datetime
    ) -> dict[RejectionReason, int]:
        stmt = (
            select(Candidate.rejection_reason, func.count(Candidate.id))
            .where(
                Candidate.status == CandidateStatus.SCREEN_REJECTED,
                Candidate.created_at >= date_from,
                Candidate.created_at < date_to,
                Candidate.rejection_reason.is_not(None),
            )
            .group_by(Candidate.rejection_reason)
        )
        return {r: c for r, c in (await self.session.execute(stmt)).all()}
