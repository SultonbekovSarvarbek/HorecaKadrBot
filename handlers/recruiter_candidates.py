"""Рекрутер/админ: /candidates с фильтрами, /candidate <id>, /set_status."""
import logging
import math
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import CandidateStatus, Position, Role, STATUSES_NEED_REASON, User
from db.repository import AuditRepo, BranchRepo, CandidateRepo
from keyboards.recruiter import branches_kb, positions_kb, status_filter_kb, statuses_kb
from services.cards import candidate_full_form
from utils.roles import RoleFilter

logger = logging.getLogger("bot.recruiter.candidates")
router = Router(name="recruiter_candidates")
router.message.filter(RoleFilter(Role.RECRUITER, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.RECRUITER, Role.ADMIN))

PER_PAGE = 5


class RecStatusReason(StatesGroup):
    reason = State()


# ── /candidates: фильтры филиал → позиция → статус → список ──────────
@router.message(Command("candidates"))
async def cmd_candidates(message: Message, session: AsyncSession) -> None:
    branches = await BranchRepo(session).all()
    await message.answer(
        texts.FILTER_BRANCH, reply_markup=branches_kb(branches, "cfb", with_all=True)
    )


@router.callback_query(F.data.startswith("cfb:"))
async def cf_branch(callback: CallbackQuery) -> None:
    await callback.answer()
    branch = callback.data.split(":", 1)[1]
    await callback.message.answer(
        texts.FILTER_POSITION, reply_markup=positions_kb(f"cfp:{branch}", with_all=True)
    )


@router.callback_query(F.data.startswith("cfp:"))
async def cf_position(callback: CallbackQuery) -> None:
    await callback.answer()
    # cfp:<branch>:<pos>
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    branch, position = parts[1], parts[2]
    await callback.message.answer(
        texts.FILTER_STATUS, reply_markup=status_filter_kb(f"cfs:{branch}:{position}")
    )


@router.callback_query(F.data.startswith("cfs:"))
async def cf_status(callback: CallbackQuery, session: AsyncSession) -> None:
    # cfs:<branch>:<pos>:<status> или clist:<branch>:<pos>:<status>:<page>
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 4:
        return
    await _show_list(callback.message, session, parts[1], parts[2], parts[3], 0)


@router.callback_query(F.data.startswith("clist:"))
async def cf_page(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 5 or not parts[4].lstrip("-").isdigit():
        return
    await _show_list(callback.message, session, parts[1], parts[2], parts[3], int(parts[4]))


async def _show_list(
    message: Message, session: AsyncSession, branch: str, position: str, status: str, page: int
) -> None:
    branch_id = int(branch) if branch.isdigit() else None
    pos = Position(position) if position != "-" else None
    st = CandidateStatus(status) if status != "-" else None
    candidates, total = await CandidateRepo(session).list_filtered(
        branch_id=branch_id, position=pos, status=st, page=page, per_page=PER_PAGE
    )
    if total == 0:
        await message.answer(texts.CAND_EMPTY)
        return
    pages = max(1, math.ceil(total / PER_PAGE))
    builder = InlineKeyboardBuilder()
    for c in candidates:
        builder.button(
            text=f"#{c.id} {c.full_name} · {texts.STATUS_LABELS[c.status]}",
            callback_data=f"ccard:{c.id}",
        )
    builder.adjust(1)
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️", callback_data=f"clist:{branch}:{position}:{status}:{page - 1}"
            )
        )
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="▶️", callback_data=f"clist:{branch}:{position}:{status}:{page + 1}"
            )
        )
    builder.row(*nav)
    await message.answer(
        texts.CAND_LIST_TITLE.format(page=page + 1, pages=pages, total=total),
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Карточка ─────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("ccard:"))
async def cb_card(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    raw = callback.data.split(":", 1)[1]
    if not raw.isdigit():
        return
    candidate = await CandidateRepo(session).by_id(int(raw))
    if candidate is None:
        await callback.message.answer(texts.CANDIDATE_NOT_FOUND)
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сменить статус", callback_data=f"cstatus:{candidate.id}")
    await callback.message.answer(
        candidate_full_form(candidate), reply_markup=builder.as_markup()
    )


@router.message(Command("candidate"))
async def cmd_candidate(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer(texts.CAND_USAGE)
        return
    candidate = await CandidateRepo(session).by_id(int(arg))
    if candidate is None:
        await message.answer(texts.CANDIDATE_NOT_FOUND)
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сменить статус", callback_data=f"cstatus:{candidate.id}")
    await message.answer(candidate_full_form(candidate), reply_markup=builder.as_markup())


# ── /set_status ──────────────────────────────────────────────────────
@router.message(Command("set_status"))
async def cmd_set_status(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    arg = (command.args or "").strip()
    if arg.isdigit():
        candidate = await CandidateRepo(session).by_id(int(arg))
        if candidate is None:
            await message.answer(texts.CANDIDATE_NOT_FOUND)
            return
        await message.answer(
            texts.CHOOSE_STATUS.format(id=candidate.id),
            reply_markup=statuses_kb(candidate.id),
        )
        return
    # без аргумента — свежие кандидаты
    candidates, total = await CandidateRepo(session).list_filtered(page=0, per_page=10)
    if total == 0:
        await message.answer(texts.CAND_EMPTY)
        return
    builder = InlineKeyboardBuilder()
    for c in candidates:
        builder.button(
            text=f"#{c.id} {c.full_name} · {texts.STATUS_LABELS[c.status]}",
            callback_data=f"cstatus:{c.id}",
        )
    builder.adjust(1)
    await message.answer("Выберите кандидата:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("cstatus:"))
async def cb_status_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    raw = callback.data.split(":", 1)[1]
    if not raw.isdigit():
        return
    await callback.message.answer(
        texts.CHOOSE_STATUS.format(id=raw), reply_markup=statuses_kb(int(raw))
    )


@router.callback_query(F.data.startswith("recst:"))
async def cb_set_status(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
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
    candidate = await CandidateRepo(session).by_id(candidate_id)
    if candidate is None:
        await callback.message.answer(texts.CANDIDATE_NOT_FOUND)
        return

    if new_status in STATUSES_NEED_REASON:
        await state.set_state(RecStatusReason.reason)
        await state.update_data(candidate_id=candidate_id, new_status=new_status.value)
        await callback.message.answer(texts.ASK_STATUS_REASON)
        return

    await _apply(callback.message, session, staff_user, candidate, new_status, None)


@router.message(RecStatusReason.reason, F.text)
async def status_reason(
    message: Message, state: FSMContext, session: AsyncSession, staff_user: User
) -> None:
    data = await state.get_data()
    await state.clear()
    if "candidate_id" not in data:
        await message.answer(texts.FORM_EXPIRED)
        return
    candidate = await CandidateRepo(session).by_id(data["candidate_id"])
    if candidate is None:
        await message.answer(texts.CANDIDATE_NOT_FOUND)
        return
    await _apply(
        message, session, staff_user, candidate,
        CandidateStatus(data["new_status"]), message.text.strip(),
    )


async def _apply(
    message: Message,
    session: AsyncSession,
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
        + (f" reason={escape(reason)}" if reason else ""),
    )
    await message.answer(
        texts.STATUS_SET.format(id=candidate.id, status=texts.STATUS_LABELS[new_status])
    )
