"""Админ-панель: списки кандидатов, карточки, статусы, собеседования, аналитика, Excel."""
import logging
import math
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message, TelegramObject
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import texts
from config import Config
from db.models import CandidateStatus, Vacancy
from db.repository import CandidateRepository, InterviewRepository
from keyboards import admin as kb
from services.analytics import build_analytics_text
from services.excel import export_candidates_xlsx
from services.scheduler import schedule_reminder
from utils.formatting import candidate_card
from utils.validators import parse_interview_datetime

logger = logging.getLogger("bot.admin")
router = Router(name="admin")

PER_PAGE = 5


class AdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, config: Config) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in config.admin_ids


router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


class AdminStates(StatesGroup):
    waiting_message = State()
    waiting_interview_dt = State()


def _parse_filters(vac: str, st: str) -> tuple[Vacancy | None, CandidateStatus | None]:
    vacancy = Vacancy(vac) if vac != "-" else None
    status = CandidateStatus(st) if st != "-" else None
    return vacancy, status


# ── Меню ─────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ADMIN_MENU, reply_markup=kb.menu_kb())


@router.callback_query(F.data == "adm:menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.ADMIN_MENU, reply_markup=kb.menu_kb())


@router.callback_query(F.data == "adm:noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Фильтры ──────────────────────────────────────────────────────────
@router.callback_query(F.data == "adm:flt_vac")
async def cb_filter_vacancy(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        texts.FILTER_VACANCY, reply_markup=kb.filter_vacancy_kb()
    )


@router.callback_query(F.data.startswith("adm:flt_st:"))
async def cb_filter_status(callback: CallbackQuery) -> None:
    vac = callback.data.split(":")[2]
    await callback.answer()
    await callback.message.edit_text(
        texts.FILTER_STATUS, reply_markup=kb.filter_status_kb(vac)
    )


# ── Список с пагинацией ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("adm:list:"))
async def cb_list(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, vac, st, page_s = callback.data.split(":")
    page = int(page_s)
    vacancy, status = _parse_filters(vac, st)

    repo = CandidateRepository(session)
    candidates, total = await repo.list_filtered(vacancy, status, page, PER_PAGE)
    await callback.answer()

    if total == 0:
        await callback.message.edit_text(
            texts.NO_CANDIDATES, reply_markup=kb.filter_status_kb(vac)
        )
        return

    pages = max(1, math.ceil(total / PER_PAGE))
    await callback.message.edit_text(
        texts.CANDIDATES_PAGE_TITLE.format(page=page + 1, pages=pages, total=total),
        reply_markup=kb.candidates_page_kb(candidates, vac, st, page, pages),
    )


# ── Карточка кандидата ───────────────────────────────────────────────
@router.callback_query(F.data.startswith("adm:card:"))
async def cb_card(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    candidate_id = int(parts[2])
    vac, st, page = parts[3], parts[4], int(parts[5])

    repo = CandidateRepository(session)
    candidate = await repo.get_by_id(candidate_id)
    await callback.answer()
    if candidate is None:
        await callback.message.edit_text(texts.NO_CANDIDATES)
        return
    await callback.message.edit_text(
        candidate_card(candidate),
        reply_markup=kb.candidate_card_kb(candidate_id, vac, st, page),
    )


# ── Смена статуса ────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("adm:setst:"))
async def cb_status_menu(callback: CallbackQuery) -> None:
    candidate_id = int(callback.data.split(":")[2])
    await callback.answer()
    await callback.message.edit_text(
        texts.CHOOSE_NEW_STATUS, reply_markup=kb.status_choice_kb(candidate_id)
    )


@router.callback_query(F.data.startswith("adm:st:"))
async def cb_set_status(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    _, _, candidate_id_s, status_s = callback.data.split(":")
    candidate_id = int(candidate_id_s)
    new_status = CandidateStatus(status_s)

    repo = CandidateRepository(session)
    candidate = await repo.get_by_id(candidate_id)
    await callback.answer()
    if candidate is None:
        return
    changed = candidate.status != new_status
    await repo.change_status(candidate, new_status)

    # некоторые статусы дублируем кандидату
    notify_text = texts.STATUS_CHANGED_FOR_CANDIDATE.get(new_status)
    if changed and notify_text:
        try:
            await bot.send_message(candidate.tg_id, notify_text)
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось уведомить кандидата %s: %s", candidate.tg_id, e)

    await callback.message.edit_text(
        candidate_card(candidate), reply_markup=kb.candidate_card_kb(candidate_id)
    )


# ── Сообщение кандидату ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("adm:msg:"))
async def cb_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    candidate_id = int(callback.data.split(":")[2])
    await state.set_state(AdminStates.waiting_message)
    await state.update_data(candidate_id=candidate_id)
    await callback.answer()
    await callback.message.answer(texts.ASK_MESSAGE_TEXT)


@router.message(AdminStates.waiting_message, Command("cancel"))
@router.message(AdminStates.waiting_interview_dt, Command("cancel"))
async def cancel_admin_action(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ACTION_CANCELLED)


@router.message(AdminStates.waiting_message, F.text)
async def send_message_to_candidate(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    await state.clear()
    repo = CandidateRepository(session)
    candidate = await repo.get_by_id(data["candidate_id"])
    if candidate is None:
        await message.answer(texts.NO_CANDIDATES)
        return
    try:
        await bot.send_message(
            candidate.tg_id, texts.HR_MESSAGE_PREFIX + message.text
        )
        await message.answer(texts.MESSAGE_SENT)
    except Exception as e:  # noqa: BLE001
        logger.warning("Сообщение кандидату %s не доставлено: %s", candidate.tg_id, e)
        await message.answer(texts.MESSAGE_SEND_FAILED)


# ── Назначение собеседования ─────────────────────────────────────────
@router.callback_query(F.data.startswith("adm:iv:"))
async def cb_interview_start(callback: CallbackQuery, state: FSMContext) -> None:
    candidate_id = int(callback.data.split(":")[2])
    await state.set_state(AdminStates.waiting_interview_dt)
    await state.update_data(candidate_id=candidate_id)
    await callback.answer()
    await callback.message.answer(texts.ASK_INTERVIEW_DT)


@router.message(AdminStates.waiting_interview_dt, F.text)
async def schedule_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    dt = parse_interview_datetime(message.text, datetime.now())
    if dt is None:
        await message.answer(texts.INVALID_INTERVIEW_DT)
        return

    data = await state.get_data()
    await state.clear()

    candidate_repo = CandidateRepository(session)
    candidate = await candidate_repo.get_by_id(data["candidate_id"])
    if candidate is None:
        await message.answer(texts.NO_CANDIDATES)
        return

    interview = await InterviewRepository(session).create(candidate.id, dt)
    await candidate_repo.change_status(candidate, CandidateStatus.INVITED)
    schedule_reminder(scheduler, bot, session_factory, interview.id, dt)

    dt_str = f"{dt:%d.%m.%Y %H:%M}"
    try:
        await bot.send_message(
            candidate.tg_id, texts.INTERVIEW_INVITATION.format(dt=dt_str)
        )
        await message.answer(texts.INTERVIEW_SCHEDULED.format(dt=dt_str))
    except Exception as e:  # noqa: BLE001
        logger.warning("Приглашение кандидату %s не доставлено: %s", candidate.tg_id, e)
        await message.answer(texts.INTERVIEW_NOTIFY_FAILED)


# ── Аналитика ────────────────────────────────────────────────────────
@router.callback_query(F.data == "adm:analytics")
async def cb_analytics(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    text = await build_analytics_text(session, datetime.now())
    await callback.message.edit_text(text, reply_markup=kb.menu_kb())


# ── Выгрузка в Excel ─────────────────────────────────────────────────
@router.callback_query(F.data == "adm:export")
async def cb_export(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    repo = CandidateRepository(session)
    candidates = await repo.list_all()
    if not candidates:
        await callback.message.answer(texts.EXPORT_EMPTY)
        return
    content = export_candidates_xlsx(candidates)
    file = BufferedInputFile(
        content, filename=f"candidates_{datetime.now():%Y%m%d_%H%M}.xlsx"
    )
    await callback.message.answer_document(
        file, caption=texts.EXPORT_CAPTION.format(count=len(candidates))
    )
