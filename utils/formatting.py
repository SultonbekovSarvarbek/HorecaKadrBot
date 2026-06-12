"""Форматирование карточек кандидатов."""
from html import escape

import texts
from db.models import Candidate


def candidate_card(c: Candidate) -> str:
    username = f"@{escape(c.username)}" if c.username else "—"
    source = escape(c.source) if c.source else "—"
    return (
        f"👤 <b>{escape(c.name)}</b> (#{c.id})\n"
        f"Вакансия: {texts.VACANCY_LABELS.get(c.vacancy, c.vacancy.value)}\n"
        f"Статус: {texts.STATUS_LABELS.get(c.status, c.status.value)}\n\n"
        f"Возраст: {c.age}\n"
        f"Телефон: {escape(c.phone)}\n"
        f"Район: {escape(c.district)}\n"
        f"Опыт: {escape(c.experience)}\n"
        f"График 6/1 или 5/2: {'Да' if c.schedule_ok else 'Нет'}\n"
        f"Готов выйти: {escape(c.start_when)}\n\n"
        f"Telegram: {username} (id {c.tg_id})\n"
        f"Источник: {source}\n"
        f"Заявка от: {c.created_at:%d.%m.%Y %H:%M}"
    )
