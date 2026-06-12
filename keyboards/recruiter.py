"""Клавиатуры рекрутера/админа."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import texts
from db.models import Branch, CandidateStatus, Position, Vacancy


def branches_kb(branches: list[Branch], prefix: str, with_all: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if with_all:
        builder.button(text=texts.FILTER_ALL, callback_data=f"{prefix}:-")
    for b in branches:
        builder.button(text=b.name, callback_data=f"{prefix}:{b.id}")
    builder.adjust(2)
    return builder.as_markup()


def positions_kb(prefix: str, with_all: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if with_all:
        builder.button(text=texts.FILTER_ALL, callback_data=f"{prefix}:-")
    for p in Position:
        builder.button(text=texts.POSITION_LABELS[p], callback_data=f"{prefix}:{p.value}")
    builder.adjust(2)
    return builder.as_markup()


def vacancies_pick_kb(vacancies: list[Vacancy], prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vacancies:
        builder.button(
            text=f"#{v.id} {texts.POSITION_LABELS[v.position]} · {v.branch.name}",
            callback_data=f"{prefix}:{v.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def statuses_kb(candidate_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for status in CandidateStatus:
        builder.button(
            text=texts.STATUS_LABELS[status],
            callback_data=f"recst:{candidate_id}:{status.value}",
        )
    builder.adjust(2)
    return builder.as_markup()


def status_filter_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.FILTER_ALL, callback_data=f"{prefix}:-")
    for status in CandidateStatus:
        builder.button(
            text=texts.STATUS_LABELS[status], callback_data=f"{prefix}:{status.value}"
        )
    builder.adjust(2)
    return builder.as_markup()
