"""Меню менеджера филиала и шеф-повара: заявки на персонал, свои кандидаты, статусы."""
import logging
import math
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import CandidateStatus, Position, Role, STATUSES_NEED_REASON, User
from db.repository import AuditRepo, CandidateRepo, StaffRequestRepo, VacancyRepo
from keyboards.manager import (
    MANAGER_STATUS_ACTIONS,
    candidates_page_kb,
    manager_candidate_kb,
    manager_menu_kb,
    positions_kb,
    staff_request_kb,
)
from services.cards import candidate_full_form
from services.notify import notify_recruiters
from utils.roles import RoleFilter
from utils.validators import validate_int

logger = logging.getLogger("bot.manager")
router = Router(name="manager")
router.message.filter(RoleFilter(Role.BRANCH_MANAGER, Role.CHEF))
router.callback_query.filter(RoleFilter(Role.BRANCH_MANAGER, Role.CHEF))

PER_PAGE = 5

# статусы «Приглашён и далее» — что видит менеджер
VISIBLE_STATUSES = [
    CandidateStatus.INVITED,
    CandidateStatus.CAME,
    CandidateStatus.NO_SHOW,
    CandidateStatus.INTERNSHIP,
    CandidateStatus.INTERNSHIP_FAILED,
    CandidateStatus.HIRED,
    CandidateStatus.EMPLOYER_REJECTED,
]


class StaffRequestForm(StatesGroup):
    position = State()
    count = State()
    comment = State()


class StatusReasonForm(StatesGroup):
    reason = State()


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer(texts.ACTION_CANCELLED)


# ── Заявка на персонал ───────────────────────────────────────────────
@router.callback_query(F.data == "mgr:request")
async def sr_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(StaffRequestForm.position)
    await callback.message.answer(
        texts.SR_ASK_POSITION, reply_markup=positions_kb("srpos")
    )


@router.callback_query(StaffRequestForm.position, F.data.startswith("srpos:"))
async def sr_position(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        position = Position(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.update_data(position=position.value)
    await state.set_state(StaffRequestForm.count)
    await callback.message.answer(texts.SR_ASK_COUNT)


@router.message(StaffRequestForm.count, F.text)
async def sr_count(message: Message, state: FSMContext) -> None:
    count = validate_int(message.text, 1, 50)
    if count is None:
        await message.answer(texts.SR_INVALID_COUNT)
        return
    await state.update_data(count=count)
    await state.set_state(StaffRequestForm.comment)
    await message.answer(texts.SR_ASK_COMMENT)


@router.message(StaffRequestForm.comment, F.text)
async def sr_comment(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    staff_user: User,
) -> None:
    data = await state.get_data()
    await state.clear()
    if "position" not in data or "count" not in data:
        await message.answer(texts.FORM_EXPIRED)
        return

    comment = "" if message.text.strip() == "-" else message.text.strip()
    branch_id = staff_user.branch_id
    if branch_id is None:  # шеф без филиала — кухня = Куйлюк по умолчанию
        from db.seed import get_cook_interview_branch

        branch = await get_cook_interview_branch(session)
        branch_id = branch.id if branch else 1

    req = await StaffRequestRepo(session).create(
        manager_tg_id=staff_user.tg_id,
        branch_id=branch_id,
        position=Position(data["position"]),
        count=data["count"],
        comment=comment,
    )
    req = await StaffRequestRepo(session).by_id(req.id)
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "staff_request_created",
        f"req={req.id} pos={req.position.value} count={req.count}",
    )
    await message.answer(texts.SR_CREATED.format(id=req.id))
    await notify_recruiters(
        bot,
        session,
        texts.SR_NEW_FOR_RECRUITER.format(
            id=req.id,
            branch=escape(req.branch.name),
            position=texts.POSITION_LABELS[req.position],
            count=req.count,
            comment=escape(comment) or "—",
            manager=escape(staff_user.name) or staff_user.tg_id,
        ),
        reply_markup=staff_request_kb(req.id),
    )


# ── Открытые вакансии моего филиала ──────────────────────────────────
@router.callback_query(F.data == "mgr:vacancies")
async def my_vacancies(
    callback: CallbackQuery, session: AsyncSession, staff_user: User
) -> None:
    await callback.answer()
    if staff_user.branch_id is None:
        await callback.message.answer(texts.MY_BRANCH_NO_VACANCIES)
        return
    repo = VacancyRepo(session)
    vacancies = await repo.open_vacancies(staff_user.branch_id)
    if not vacancies:
        await callback.message.answer(texts.MY_BRANCH_NO_VACANCIES)
        return
    hired = await repo.hired_counts([v.id for v in vacancies])
    branch_name = staff_user.branch.name if staff_user.branch else "—"
    lines = [texts.MY_BRANCH_VACANCIES_TITLE.format(branch=escape(branch_name))]
    for v in vacancies:
        lines.append(
            f"#{v.id} {texts.POSITION_LABELS[v.position]} · "
            f"закрыто {hired.get(v.id, 0)}/{v.quota} · {escape(v.salary) or '—'}"
        )
    await callback.message.answer("\n".join(lines))


# ── Мои кандидаты ────────────────────────────────────────────────────
async def _list_candidates(session: AsyncSession, staff_user: User, page: int):
    repo = CandidateRepo(session)
    if staff_user.role == Role.CHEF:
        # шеф видит поваров всех филиалов
        return await repo.list_filtered(
            position=Position.COOK, statuses=VISIBLE_STATUSES,
            page=page, per_page=PER_PAGE,
        )
    return await repo.list_filtered(
        branch_id=staff_user.branch_id, statuses=VISIBLE_STATUSES,
        page=page, per_page=PER_PAGE,
    )


@router.callback_query(F.data.startswith("mgr:cands:"))
async def my_candidates(
    callback: CallbackQuery, session: AsyncSession, staff_user: User
) -> None:
    await callback.answer()
    try:
        page = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        page = 0
    candidates, total = await _list_candidates(session, staff_user, page)
    if total == 0:
        await callback.message.answer(texts.MY_CANDIDATES_EMPTY)
        return
    pages = max(1, math.ceil(total / PER_PAGE))
    await callback.message.answer(
        texts.CAND_LIST_TITLE.format(page=page + 1, pages=pages, total=total),
        reply_markup=candidates_page_kb(candidates, page, pages),
    )


def _can_manage(staff_user: User, candidate) -> bool:
    """Менеджер — только свой филиал; шеф — только поваров."""
    if staff_user.role == Role.CHEF:
        return candidate.vacancy.position == Position.COOK
    return candidate.vacancy.branch_id == staff_user.branch_id


@router.callback_query(F.data.startswith("mgr:card:"))
async def candidate_card_view(
    callback: CallbackQuery, session: AsyncSession, staff_user: User
) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 4 or not parts[2].isdigit():
        return
    candidate_id, page = int(parts[2]), int(parts[3]) if parts[3].isdigit() else 0
    candidate = await CandidateRepo(session).by_id(candidate_id)
    if candidate is None or not _can_manage(staff_user, candidate):
        await callback.message.answer(texts.CANDIDATE_NOT_FOUND)
        return
    await callback.message.answer(
        candidate_full_form(candidate) + f"\n\n{texts.MANAGER_STATUS_BUTTONS_HINT}",
        reply_markup=manager_candidate_kb(candidate_id, page),
    )


# ── Смена статуса менеджером ─────────────────────────────────────────
@router.callback_query(F.data.startswith("mgrst:"))
async def manager_set_status(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    staff_user: User,
) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit():
        return
    candidate_id = int(parts[1])
    try:
        new_status = CandidateStatus(parts[2])
    except ValueError:
        return
    if new_status not in MANAGER_STATUS_ACTIONS:
        return
    candidate = await CandidateRepo(session).by_id(candidate_id)
    if candidate is None or not _can_manage(staff_user, candidate):
        await callback.message.answer(texts.CANDIDATE_NOT_FOUND)
        return

    if new_status in STATUSES_NEED_REASON:
        await state.set_state(StatusReasonForm.reason)
        await state.update_data(candidate_id=candidate_id, new_status=new_status.value)
        await callback.message.answer(texts.ASK_STATUS_REASON)
        return

    await _apply_status(callback.message, session, bot, staff_user, candidate, new_status, None)


@router.message(StatusReasonForm.reason, F.text)
async def status_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    staff_user: User,
) -> None:
    data = await state.get_data()
    await state.clear()
    if "candidate_id" not in data:
        await message.answer(texts.FORM_EXPIRED)
        return
    candidate = await CandidateRepo(session).by_id(data["candidate_id"])
    if candidate is None or not _can_manage(staff_user, candidate):
        await message.answer(texts.CANDIDATE_NOT_FOUND)
        return
    await _apply_status(
        message, session, bot, staff_user, candidate,
        CandidateStatus(data["new_status"]), message.text.strip(),
    )


async def _apply_status(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    staff_user: User,
    candidate,
    new_status: CandidateStatus,
    reason: str | None,
) -> None:
    old = candidate.status
    await CandidateRepo(session).change_status(
        candidate, new_status, changed_by_tg=staff_user.tg_id, reason=reason
    )
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "status_change",
        f"cand={candidate.id} {old.value}->{new_status.value}"
        + (f" reason={reason}" if reason else ""),
    )
    await message.answer(
        texts.STATUS_SET.format(id=candidate.id, status=texts.STATUS_LABELS[new_status])
    )
    # дублируем рекрутеру
    who = escape(staff_user.name) or str(staff_user.tg_id)
    await notify_recruiters(
        bot,
        session,
        texts.STATUS_CHANGE_FOR_RECRUITER.format(
            who=f"{texts.ROLE_LABELS[staff_user.role]} {who}",
            id=candidate.id,
            name=escape(candidate.full_name),
            old=texts.STATUS_LABELS[old],
            new=texts.STATUS_LABELS[new_status],
            reason=f" (причина: {escape(reason)})" if reason else "",
        ),
    )
