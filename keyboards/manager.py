"""Клавиатуры менеджера филиала и шеф-повара."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import texts
from db.models import CandidateStatus, Position


def manager_menu_kb(chef: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_STAFF_REQUEST, callback_data="mgr:request")
    if not chef:
        builder.button(text=texts.BTN_MY_VACANCIES, callback_data="mgr:vacancies")
    builder.button(text=texts.BTN_MY_CANDIDATES, callback_data="mgr:cands:0")
    builder.adjust(1)
    return builder.as_markup()


def positions_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in Position:
        builder.button(text=texts.POSITION_LABELS[p], callback_data=f"{prefix}:{p.value}")
    builder.adjust(2)
    return builder.as_markup()


# Статусы, которые менеджер ставит сам
MANAGER_STATUS_ACTIONS: list[CandidateStatus] = [
    CandidateStatus.CAME,
    CandidateStatus.NO_SHOW,
    CandidateStatus.INTERNSHIP,
    CandidateStatus.INTERNSHIP_FAILED,
    CandidateStatus.HIRED,
]


def manager_candidate_kb(candidate_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for status in MANAGER_STATUS_ACTIONS:
        builder.button(
            text=texts.STATUS_LABELS[status],
            callback_data=f"mgrst:{candidate_id}:{status.value}",
        )
    builder.adjust(2)
    builder.button(text=texts.BTN_BACK, callback_data=f"mgr:cands:{page}")
    return builder.as_markup()


def candidates_page_kb(candidates, page: int, pages: int) -> InlineKeyboardMarkup:
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    for c in candidates:
        builder.button(
            text=f"#{c.id} {c.full_name} · {texts.STATUS_LABELS[c.status]}",
            callback_data=f"mgr:card:{c.id}:{page}",
        )
    builder.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"mgr:cands:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"mgr:cands:{page + 1}"))
    builder.row(*nav)
    return builder.as_markup()


def staff_request_kb(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.SR_BTN_CREATE_VACANCY, callback_data=f"sr:create:{request_id}")
    builder.button(text=texts.SR_BTN_CLARIFY, callback_data=f"sr:clarify:{request_id}")
    builder.button(text=texts.SR_BTN_REJECT, callback_data=f"sr:reject:{request_id}")
    builder.adjust(1)
    return builder.as_markup()
