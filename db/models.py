"""Модели БД: Branches, Vacancies, Candidates, Users, StaffRequests,
StatusLog, AuditLog, Settings."""
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from utils.timeutil import now_local


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ── Справочники-перечисления ─────────────────────────────────────────
class Role(str, enum.Enum):
    RECRUITER = "recruiter"
    BRANCH_MANAGER = "branch_manager"
    CHEF = "chef"
    ADMIN = "admin"


class Position(str, enum.Enum):
    WAITER = "waiter"
    BARTENDER = "bartender"
    COOK = "cook"
    TECH = "tech"


class CookSpec(str, enum.Enum):
    HOT = "hot"
    COLD = "cold"
    SUSHI = "sushi"
    UNIVERSAL = "universal"
    OTHER = "other"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class RussianLevel(str, enum.Enum):
    FLUENT = "fluent"
    MIDDLE = "middle"
    NONE = "none"


class CandidateStatus(str, enum.Enum):
    NEW = "new"
    SCREEN_REJECTED = "screen_rejected"      # Отказ по критериям
    INVITED = "invited"                      # Приглашён
    CAME = "came"                            # Пришёл на собеседование
    NO_SHOW = "no_show"                      # Не пришёл
    INTERNSHIP = "internship"                # Вышел на стажировку
    INTERNSHIP_FAILED = "internship_failed"  # Не прошёл стажировку
    HIRED = "hired"                          # Принят
    EMPLOYER_REJECTED = "employer_rejected"  # Отказ работодателя
    NOT_INTERESTED = "not_interested"        # Не заинтересован


class RejectionReason(str, enum.Enum):
    AGE = "age"
    EXPERIENCE = "experience"
    LANGUAGE = "language"
    MILITARY = "military"
    PORK_ALCOHOL = "pork_alcohol"


class VacancyStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class StaffRequestStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CONVERTED = "converted"
    REJECTED = "rejected"


# Этапы воронки по порядку (для конверсии)
FUNNEL_ORDER: list[CandidateStatus] = [
    CandidateStatus.NEW,
    CandidateStatus.INVITED,
    CandidateStatus.CAME,
    CandidateStatus.INTERNSHIP,
    CandidateStatus.HIRED,
]

TERMINAL_STATUSES: frozenset[CandidateStatus] = frozenset(
    {
        CandidateStatus.SCREEN_REJECTED,
        CandidateStatus.NO_SHOW,
        CandidateStatus.INTERNSHIP_FAILED,
        CandidateStatus.HIRED,
        CandidateStatus.EMPLOYER_REJECTED,
        CandidateStatus.NOT_INTERESTED,
    }
)

# Статусы, требующие обязательной причины при установке
STATUSES_NEED_REASON: frozenset[CandidateStatus] = frozenset(
    {CandidateStatus.EMPLOYER_REJECTED, CandidateStatus.INTERNSHIP_FAILED}
)


# ── Таблицы ──────────────────────────────────────────────────────────
class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(String(256), default="адрес уточняется")
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="branch")


class User(Base):
    """Whitelist сотрудников: рекрутеры, менеджеры, шеф, админы."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[Role] = mapped_column(Enum(Role), index=True)
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    branch: Mapped[Branch | None] = relationship()


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    position: Mapped[Position] = mapped_column(Enum(Position), index=True)
    salary: Mapped[str] = mapped_column(String(128), default="")
    schedule: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    quota: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus), default=VacancyStatus.OPEN, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    branch: Mapped[Branch] = relationship(back_populates="vacancies")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="vacancy")


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint("age >= 14 AND age <= 80", name="ck_candidates_age_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(160))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    phone: Mapped[str] = mapped_column(String(32))
    district: Mapped[str] = mapped_column(String(64))
    # опыт: категория для всех, для поваров — стаж в годах + специализация
    experience_cat: Mapped[str] = mapped_column(String(32), default="")
    cook_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_spec: Mapped[CookSpec | None] = mapped_column(Enum(CookSpec), nullable=True)
    russian: Mapped[RussianLevel] = mapped_column(Enum(RussianLevel))
    pork_alcohol_ok: Mapped[bool] = mapped_column(Boolean)
    military_id: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.NEW, index=True
    )
    rejection_reason: Mapped[RejectionReason | None] = mapped_column(
        Enum(RejectionReason), nullable=True
    )
    status_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # причина отказа работодателя / провала стажировки
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, onupdate=now_local
    )

    vacancy: Mapped[Vacancy] = relationship(back_populates="candidates")
    status_logs: Mapped[list["StatusLog"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class StaffRequest(Base):
    """Заявка менеджера филиала на персонал."""

    __tablename__ = "staff_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manager_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    position: Mapped[Position] = mapped_column(Enum(Position))
    count: Mapped[int] = mapped_column(Integer, default=1)
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[StaffRequestStatus] = mapped_column(
        Enum(StaffRequestStatus), default=StaffRequestStatus.NEW
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    branch: Mapped[Branch] = relationship()


class StatusLog(Base):
    __tablename__ = "status_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    old_status: Mapped[CandidateStatus | None] = mapped_column(
        Enum(CandidateStatus), nullable=True
    )
    new_status: Mapped[CandidateStatus] = mapped_column(Enum(CandidateStatus))
    changed_by_tg: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    candidate: Mapped[Candidate] = relationship(back_populates="status_logs")


class AuditLog(Base):
    """Лог действий рекрутеров/менеджеров/админов."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class Setting(Base):
    """Ключ-значение: пороги скрининга, chat_id кухни, ссылки."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
