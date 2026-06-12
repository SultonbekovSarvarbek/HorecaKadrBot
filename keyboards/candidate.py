"""Клавиатуры воронки кандидата."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import texts
from db.models import Vacancy

BACK_CB = "form:back"


def vacancies_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for vacancy in Vacancy:
        builder.button(
            text=texts.VACANCY_LABELS[vacancy], callback_data=f"vacancy:{vacancy.value}"
        )
    builder.adjust(2)
    return builder.as_markup()


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB)]]
    )


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
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB))
    return builder.as_markup()


def experience_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(texts.EXPERIENCE_OPTIONS):
        builder.button(text=option, callback_data=f"exp:{i}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB))
    return builder.as_markup()


def schedule_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_YES, callback_data="schedule:yes")
    builder.button(text=texts.BTN_NO, callback_data="schedule:no")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB))
    return builder.as_markup()


def start_when_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(texts.START_WHEN_OPTIONS):
        builder.button(text=option, callback_data=f"when:{i}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=BACK_CB))
    return builder.as_markup()
