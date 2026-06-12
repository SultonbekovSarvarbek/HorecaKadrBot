"""Отчёты: /report — FSM период → филиал → позиция → сводка + Excel."""
import logging
from datetime import timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import Position, RejectionReason, Role
from db.repository import BranchRepo, ReportRepo
from keyboards.recruiter import branches_kb, positions_kb
from services.export import export_candidates_xlsx
from utils.roles import RoleFilter
from utils.validators import parse_date

logger = logging.getLogger("bot.reports")
router = Router(name="reports")
router.message.filter(RoleFilter(Role.RECRUITER, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.RECRUITER, Role.ADMIN))


class ReportForm(StatesGroup):
    date_from = State()
    date_to = State()
    branch = State()
    position = State()


@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ReportForm.date_from)
    await message.answer(texts.REPORT_ASK_FROM)


@router.message(ReportForm.date_from, F.text)
async def report_from(message: Message, state: FSMContext) -> None:
    dt = parse_date(message.text)
    if dt is None:
        await message.answer(texts.REPORT_INVALID_DATE)
        return
    await state.update_data(date_from=dt.strftime("%Y%m%d"))
    await state.set_state(ReportForm.date_to)
    await message.answer(texts.REPORT_ASK_TO)


@router.message(ReportForm.date_to, F.text)
async def report_to(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    dt = parse_date(message.text)
    if dt is None:
        await message.answer(texts.REPORT_INVALID_DATE)
        return
    await state.update_data(date_to=dt.strftime("%Y%m%d"))
    await state.set_state(ReportForm.branch)
    branches = await BranchRepo(session).all()
    await message.answer(
        texts.REPORT_ASK_BRANCH, reply_markup=branches_kb(branches, "rbr", with_all=True)
    )


@router.callback_query(ReportForm.branch, F.data.startswith("rbr:"))
async def report_branch(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(branch=callback.data.split(":", 1)[1])
    await state.set_state(ReportForm.position)
    await callback.message.answer(
        texts.REPORT_ASK_POSITION, reply_markup=positions_kb("rpos", with_all=True)
    )


@router.callback_query(ReportForm.position, F.data.startswith("rpos:"))
async def report_position(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    if "date_from" not in data or "date_to" not in data:
        await callback.message.answer(texts.FORM_EXPIRED)
        return
    branch = data.get("branch", "-")
    position = callback.data.split(":", 1)[1]
    await _send_report(
        callback.message, session, data["date_from"], data["date_to"], branch, position
    )


def _pct(part: int, total: int) -> str:
    return f"{part / total * 100:.0f}" if total else "0"


async def _send_report(
    message: Message,
    session: AsyncSession,
    from_s: str,
    to_s: str,
    branch: str,
    position: str,
) -> None:
    from datetime import datetime

    date_from = datetime.strptime(from_s, "%Y%m%d")
    date_to = datetime.strptime(to_s, "%Y%m%d") + timedelta(days=1)  # включительно
    branch_id = int(branch) if branch.isdigit() else None
    pos = Position(position) if position != "-" else None

    repo = ReportRepo(session)
    data = await repo.funnel(date_from, date_to, branch_id, pos)

    branch_name = texts.FILTER_ALL
    if branch_id is not None:
        b = await BranchRepo(session).by_id(branch_id)
        branch_name = b.name if b else "?"
    pos_name = texts.POSITION_LABELS[pos] if pos else texts.FILTER_ALL

    rejected_total = sum(data["rejections"].values())
    rejection_lines = "\n".join(
        f"• {texts.REJECTION_LABELS[r]}: {cnt}"
        for r, cnt in sorted(data["rejections"].items(), key=lambda x: -x[1])
    ) or "• —"
    source_lines = "\n".join(
        f"• {escape(str(src))}: {cnt}"
        for src, cnt in sorted(data["sources"].items(), key=lambda x: -x[1])
    ) or "• —"

    applied = data["applied"]
    text = texts.REPORT_TEMPLATE.format(
        date_from=date_from.strftime("%d.%m.%Y"),
        date_to=(date_to - timedelta(days=1)).strftime("%d.%m.%Y"),
        branch=escape(branch_name),
        position=pos_name,
        applied=applied,
        screened=data["screened"], screened_pct=_pct(data["screened"], applied),
        came=data["came"], came_pct=_pct(data["came"], applied),
        internship=data["internship"], internship_pct=_pct(data["internship"], applied),
        hired=data["hired"], hired_pct=_pct(data["hired"], applied),
        rejected_total=rejected_total,
        rejections=rejection_lines + "\n",
        sources=source_lines,
    )
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.BTN_DOWNLOAD_EXCEL,
        callback_data=f"rexcel:{from_s}:{to_s}:{branch}:{position}",
    )
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("rexcel:"))
async def report_excel(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 5:
        return
    from datetime import datetime

    try:
        date_from = datetime.strptime(parts[1], "%Y%m%d")
        date_to = datetime.strptime(parts[2], "%Y%m%d") + timedelta(days=1)
    except ValueError:
        return
    branch_id = int(parts[3]) if parts[3].isdigit() else None
    pos = Position(parts[4]) if parts[4] != "-" else None

    candidates = await ReportRepo(session).candidates_full(
        date_from, date_to, branch_id, pos
    )
    if not candidates:
        await callback.message.answer(texts.EXPORT_EMPTY)
        return
    content = export_candidates_xlsx(candidates)
    file = BufferedInputFile(
        content, filename=f"chenson_{parts[1]}_{parts[2]}.xlsx"
    )
    await callback.message.answer_document(
        file, caption=texts.EXPORT_CAPTION.format(count=len(candidates))
    )
