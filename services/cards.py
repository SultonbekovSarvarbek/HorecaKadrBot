"""Форматирование карточек кандидатов (только для служебных чатов)."""
from html import escape

import texts
from db.models import Candidate, Position


def experience_brief(c: Candidate) -> str:
    if c.vacancy.position == Position.COOK:
        spec = texts.COOK_SPEC_LABELS.get(c.cook_spec, "—") if c.cook_spec else "—"
        return f"{c.cook_years or 0} лет, {spec}"
    return c.experience_cat or "—"


def candidate_card(c: Candidate) -> str:
    """Полная карточка. Содержит персональные данные — только в служебные чаты!"""
    username = f"@{escape(c.username)}" if c.username else "—"
    return (
        f"👤 <b>{escape(c.full_name)}</b> (#{c.id})\n"
        f"{c.age} лет · {texts.GENDER_LABELS.get(c.gender, '—')}\n"
        f"Вакансия: {texts.POSITION_LABELS.get(c.vacancy.position, '—')} · "
        f"{escape(c.vacancy.branch.name)}\n"
        f"Опыт: {escape(experience_brief(c))}\n"
        f"Район: {escape(c.district)}\n"
        f"Русский: {texts.RUSSIAN_LABELS.get(c.russian, '—')}\n"
        f"📞 {escape(c.phone)} · {username}\n"
        f"Статус: {texts.STATUS_LABELS.get(c.status, c.status.value)}\n"
        f"Источник: {escape(c.source) if c.source else '—'} · "
        f"{c.created_at:%d.%m.%Y %H:%M}"
    )


def candidate_full_form(c: Candidate) -> str:
    """Анкета целиком для /candidate <id>."""
    military = "—"
    if c.military_id is not None:
        military = "Да" if c.military_id else "Нет"
    reason = ""
    if c.rejection_reason:
        reason = f"\nПричина отказа: {texts.REJECTION_LABELS.get(c.rejection_reason, '—')}"
    if c.status_reason:
        reason += f"\nКомментарий: {escape(c.status_reason)}"
    return (
        candidate_card(c)
        + "\n\n"
        + f"Свинина/алкоголь: {'Да' if c.pork_alcohol_ok else 'Нет'}\n"
        + f"Военный билет: {military}"
        + reason
    )
