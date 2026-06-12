"""Клавиатуры админ-панели."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import texts
from db.models import CandidateStatus, Vacancy

# callback-схема:
#   adm:menu                          — главное меню
#   adm:flt_vac                       — выбор фильтра по вакансии
#   adm:flt_st:<vac|->                — выбор фильтра по статусу
#   adm:list:<vac|->:<st|->:<page>    — страница списка
#   adm:card:<id>:<vac|->:<st|->:<page> — карточка (с контекстом возврата)
#   adm:setst:<id>                    — меню смены статуса
#   adm:st:<id>:<status>              — установить статус
#   adm:msg:<id>                      — написать кандидату
#   adm:iv:<id>                       — назначить собеседование
#   adm:analytics / adm:export


def menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.ADMIN_BTN_CANDIDATES, callback_data="adm:flt_vac")
    builder.button(text=texts.ADMIN_BTN_ANALYTICS, callback_data="adm:analytics")
    builder.button(text=texts.ADMIN_BTN_EXPORT, callback_data="adm:export")
    builder.adjust(1)
    return builder.as_markup()


def filter_vacancy_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.FILTER_ALL, callback_data="adm:flt_st:-")
    for vacancy in Vacancy:
        builder.button(
            text=texts.VACANCY_LABELS[vacancy],
            callback_data=f"adm:flt_st:{vacancy.value}",
        )
    builder.adjust(1, 2, 2)
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data="adm:menu"))
    return builder.as_markup()


def filter_status_kb(vac: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.FILTER_ALL, callback_data=f"adm:list:{vac}:-:0")
    for status in CandidateStatus:
        builder.button(
            text=texts.STATUS_LABELS[status],
            callback_data=f"adm:list:{vac}:{status.value}:0",
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data="adm:flt_vac"))
    return builder.as_markup()


def candidates_page_kb(
    candidates, vac: str, st: str, page: int, pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in candidates:
        builder.button(
            text=f"{c.name} · {texts.VACANCY_LABELS[c.vacancy]}",
            callback_data=f"adm:card:{c.id}:{vac}:{st}:{page}",
        )
    builder.adjust(1)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️", callback_data=f"adm:list:{vac}:{st}:{page - 1}"
            )
        )
    nav.append(
        InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="adm:noop")
    )
    if page < pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="▶️", callback_data=f"adm:list:{vac}:{st}:{page + 1}"
            )
        )
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=f"adm:flt_st:{vac}"))
    return builder.as_markup()


def candidate_card_kb(
    candidate_id: int, vac: str = "-", st: str = "-", page: int = 0
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.CARD_BTN_STATUS, callback_data=f"adm:setst:{candidate_id}")
    builder.button(text=texts.CARD_BTN_MESSAGE, callback_data=f"adm:msg:{candidate_id}")
    builder.button(
        text=texts.CARD_BTN_INTERVIEW, callback_data=f"adm:iv:{candidate_id}"
    )
    builder.button(
        text=texts.CARD_BTN_BACK_TO_LIST,
        callback_data=f"adm:list:{vac}:{st}:{page}",
    )
    builder.adjust(1)
    return builder.as_markup()


def status_choice_kb(candidate_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for status in CandidateStatus:
        builder.button(
            text=texts.STATUS_LABELS[status],
            callback_data=f"adm:st:{candidate_id}:{status.value}",
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text=texts.BTN_BACK, callback_data=f"adm:card:{candidate_id}:-:-:0"
        )
    )
    return builder.as_markup()


def new_application_kb(candidate_id: int) -> InlineKeyboardMarkup:
    """Кнопки под уведомлением о новой заявке."""
    return candidate_card_kb(candidate_id)
