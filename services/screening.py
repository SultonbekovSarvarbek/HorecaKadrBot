"""Автоскрининг кандидатов. Все пороги — из Settings (БД) с дефолтами в config.py."""
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Gender, Position, RejectionReason, RussianLevel
from db.repository import SettingsRepo


@dataclass
class ScreeningInput:
    position: Position
    age: int
    gender: Gender
    russian: RussianLevel
    pork_alcohol_ok: bool
    military_id: bool | None  # None для женщин
    cook_years: int | None = None


@dataclass
class ScreeningResult:
    passed: bool
    reason: RejectionReason | None = None


# Префиксы ключей настроек по позициям (отдельные блоки в конфиге)
_AGE_KEY_PREFIX = {
    Position.WAITER: "waiter",
    Position.BARTENDER: "bartender",
    Position.TECH: "tech",
    Position.COOK: "cook",
}


async def screen(session: AsyncSession, data: ScreeningInput) -> ScreeningResult:
    settings = SettingsRepo(session)
    prefix = _AGE_KEY_PREFIX[data.position]

    # возраст
    age_min = await settings.get_int(f"{prefix}_age_min")
    age_max = await settings.get_int(f"{prefix}_age_max")
    if data.position == Position.COOK and data.gender == Gender.FEMALE:
        age_max = await settings.get_int("cook_age_max_female", age_max)
    if not age_min <= data.age <= age_max:
        return ScreeningResult(False, RejectionReason.AGE)

    # опыт (только повара)
    if data.position == Position.COOK:
        min_years = await settings.get_int("cook_min_exp_years")
        if (data.cook_years or 0) < min_years:
            return ScreeningResult(False, RejectionReason.EXPERIENCE)

    # язык
    if data.russian == RussianLevel.NONE:
        return ScreeningResult(False, RejectionReason.LANGUAGE)

    # военный билет (мужчины, все позиции)
    if data.gender == Gender.MALE and not data.military_id:
        return ScreeningResult(False, RejectionReason.MILITARY)

    # свинина/алкоголь
    if not data.pork_alcohol_ok:
        return ScreeningResult(False, RejectionReason.PORK_ALCOHOL)

    return ScreeningResult(True)
