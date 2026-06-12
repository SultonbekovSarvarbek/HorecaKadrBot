"""Клавиатуры воронки кандидата."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import texts
from db.models import CookSpec, Gender, RussianLevel, Vacancy

BACK_CB = "form:back"


def start_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_APPLY, callback_data="cand:apply")
    builder.button(text=texts.BTN_VACANCY_LIST, callback_data="cand:vacancies")
    builder.button(text=texts.BTN_CONDITIONS, callback_data="cand:conditions")
    builder.adjust(1)
    return builder.as_markup()


def vacancies_kb(vacancies: list[Vacancy]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vacancies:
        builder.button(
            text=f"{texts.POSITION_LABELS[v.position]} · {v.branch.name}",
            callback_data=f"vac:{v.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def _with_back(builder: InlineKeyboardBuilder) -> InlineKeyboardMarkup:
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB))
    return builder.as_markup()


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB)]]
    )


def gender_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in Gender:
        builder.button(text=texts.GENDER_LABELS[g], callback_data=f"gender:{g.value}")
    builder.adjust(2)
    return _with_back(builder)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_SHARE_CONTACT, request_contact=True)],
            [KeyboardButton(text=texts.BTN_BACK)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def districts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, district in enumerate(texts.DISTRICTS):
        builder.button(text=district, callback_data=f"district:{i}")
    builder.adjust(2)
    return _with_back(builder)


def experience_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(texts.EXPERIENCE_OPTIONS):
        builder.button(text=option, callback_data=f"exp:{i}")
    builder.adjust(2)
    return _with_back(builder)


def cook_spec_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for spec in CookSpec:
        builder.button(
            text=texts.COOK_SPEC_LABELS[spec], callback_data=f"spec:{spec.value}"
        )
    builder.adjust(2)
    return _with_back(builder)


def russian_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lvl in RussianLevel:
        builder.button(text=texts.RUSSIAN_LABELS[lvl], callback_data=f"rus:{lvl.value}")
    builder.adjust(3)
    return _with_back(builder)


def yes_no_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_YES, callback_data=f"{prefix}:yes")
    builder.button(text=texts.BTN_NO, callback_data=f"{prefix}:no")
    builder.adjust(2)
    return _with_back(builder)


def confirm_interview_kb(candidate_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_CONFIRM_COME, callback_data=f"confirm:yes:{candidate_id}")
    builder.button(text=texts.BTN_DECLINE_COME, callback_data=f"confirm:no:{candidate_id}")
    builder.adjust(2)
    return builder.as_markup()


def decline_offer_kb(candidate_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.BTN_OTHER_VACANCIES, callback_data=f"declined:other:{candidate_id}"
    )
    builder.button(
        text=texts.BTN_NOT_INTERESTED, callback_data=f"declined:bye:{candidate_id}"
    )
    builder.adjust(1)
    return builder.as_markup()
