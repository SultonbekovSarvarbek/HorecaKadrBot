"""Модели БД: Candidate, Interview, StatusLog."""
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
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from utils.timeutil import now_local


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Vacancy(str, enum.Enum):
    WAITER = "waiter"
    BARTENDER = "bartender"
    COOK = "cook"
    TECH = "tech"


class CandidateStatus(str, enum.Enum):
    NEW = "new"
    SCREENED = "screened"
    INVITED = "invited"
    CAME = "came"
    INTERNSHIP = "internship"
    HIRED = "hired"
    # терминальные
    REJECTED = "rejected"
    NO_SHOW = "no_show"
    DECLINED = "declined"


# Порядок этапов воронки (для аналитики конверсии)
FUNNEL_ORDER: list[CandidateStatus] = [
    CandidateStatus.NEW,
    CandidateStatus.SCREENED,
    CandidateStatus.INVITED,
    CandidateStatus.CAME,
    CandidateStatus.INTERNSHIP,
    CandidateStatus.HIRED,
]

TERMINAL_STATUSES: frozenset[CandidateStatus] = frozenset(
    {CandidateStatus.REJECTED, CandidateStatus.NO_SHOW, CandidateStatus.DECLINED}
)


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint("age >= 16 AND age <= 65", name="ck_candidates_age_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    age: Mapped[int] = mapped_column(Integer)
    phone: Mapped[str] = mapped_column(String(32))
    district: Mapped[str] = mapped_column(String(64))
    vacancy: Mapped[Vacancy] = mapped_column(Enum(Vacancy), index=True)
    experience: Mapped[str] = mapped_column(String(32))
    schedule_ok: Mapped[bool] = mapped_column(Boolean)
    start_when: Mapped[str] = mapped_column(String(32))
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.NEW, index=True
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, onupdate=now_local
    )

    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    status_logs: Mapped[list["StatusLog"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    datetime: Mapped[datetime] = mapped_column(DateTime)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)

    candidate: Mapped[Candidate] = relationship(back_populates="interviews")


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
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    candidate: Mapped[Candidate] = relationship(back_populates="status_logs")
