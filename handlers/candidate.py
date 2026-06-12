"""Воронка кандидата: меню, выбор вакансии, FSM-анкета, скрининг, подтверждение."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import (
    CandidateStatus,
    CookSpec,
    Gender,
    Position,
    RussianLevel,
    VacancyStatus,
)
from db.repository import CandidateRepo, VacancyRepo
from db.seed import get_cook_interview_branch
from keyboards import candidate as kb
from services.notify import send_invited_card
from services.screening import ScreeningInput, screen
from utils.validators import (
    parse_index,
    validate_age,
    validate_int,
    validate_name,
    validate_phone,
)

logger = logging.getLogger("bot.candidate")
router = Router(name="candidate")


class Form(StatesGroup):
    full_name = State()
    age = State()
    gender = State()
    phone = State()
    district = State()
    experience = State()
    cook_years = State()
    cook_spec = State()
    russian = State()
    pork_alcohol = State()
    military = State()


_STEP_BY_NAME: dict[str, State] = {
    "full_name": Form.full_name,
    "age": Form.age,
    "gender": Form.gender,
    "phone": Form.phone,
    "district": Form.district,
    "experience": Form.experience,
    "cook_years": Form.cook_years,
    "cook_spec": Form.cook_spec,
    "russian": Form.russian,
    "pork_alcohol": Form.pork_alcohol,
    "military": Form.military,
}


def _build_steps(is_cook: bool, is_male: bool | None) -> list[str]:
    """Последовательность шагов: у поваров стаж+специализация, у мужчин — военник."""
    steps = ["full_name", "age", "gender", "phone", "district"]
    steps += ["cook_years", "cook_spec"] if is_cook else ["experience"]
    steps += ["russian", "pork_alcohol"]
    if is_male:
        steps.append("military")
    return steps


async def _ask_step(message: Message, state: FSMContext, step_name: str) -> None:
    await state.set_state(_STEP_BY_NAME[step_name])
    prompts = {
        "full_name": (texts.ASK_FULL_NAME, kb.back_kb()),
        "age": (texts.ASK_AGE, kb.back_kb()),
        "gender": (texts.ASK_GENDER, kb.gender_kb()),
        "phone": (texts.ASK_PHONE, kb.phone_kb()),
        "district": (texts.ASK_DISTRICT, kb.districts_kb()),
        "experience": (texts.ASK_EXPERIENCE, kb.experience_kb()),
        "cook_years": (texts.ASK_COOK_YEARS, kb.back_kb()),
        "cook_spec": (texts.ASK_COOK_SPEC, kb.cook_spec_kb()),
        "russian": (texts.ASK_RUSSIAN, kb.russian_kb()),
        "pork_alcohol": (texts.ASK_PORK_ALCOHOL, kb.yes_no_kb("pork")),
        "military": (texts.ASK_MILITARY, kb.yes_no_kb("mil")),
    }
    text, markup = prompts[step_name]
    await message.answer(text, reply_markup=markup)


async def _goto_next(
    message: Message,
    state: FSMContext,
    current: str,
    session: AsyncSession,
    bot: Bot,
) -> None:
    data = await state.get_data()
    steps = _build_steps(data.get("is_cook", False), data.get("is_male"))
    idx = steps.index(current)
    if idx + 1 < len(steps):
        await _ask_step(message, state, steps[idx + 1])
    else:
        await _finalize(message, state, session, bot)


# ── Меню кандидата ───────────────────────────────────────────────────
async def show_candidate_menu(message: Message) -> None:
    await message.answer(texts.WELCOME_CANDIDATE, reply_markup=kb.start_menu_kb())


@router.callback_query(F.data == "cand:conditions")
async def cb_conditions(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(texts.CONDITIONS_TEXT)


@router.callback_query(F.data == "cand:vacancies")
async def cb_vacancy_list(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    vacancies = await VacancyRepo(session).open_vacancies()
    if not vacancies:
        await callback.message.answer(texts.NO_OPEN_VACANCIES)
        return
    lines = [
        f"<b>{texts.POSITION_LABELS[v.position]}</b> · {escape(v.branch.name)}\n"
        f"💰 {escape(v.salary) or '—'} · 🗓 {escape(v.schedule) or '—'}"
        for v in vacancies
    ]
    await callback.message.answer(
        "\n\n".join(lines) + f"\n\n{texts.CHOOSE_VACANCY}",
        reply_markup=kb.vacancies_kb(vacancies),
    )


@router.callback_query(F.data == "cand:apply")
async def cb_apply(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if await CandidateRepo(session).active_application(callback.from_user.id):
        await callback.message.answer(texts.ALREADY_APPLIED)
        return
    vacancies = await VacancyRepo(session).open_vacancies()
    if not vacancies:
        await callback.message.answer(texts.NO_OPEN_VACANCIES)
        return
    await callback.message.answer(
        texts.CHOOSE_VACANCY, reply_markup=kb.vacancies_kb(vacancies)
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer(texts.FORM_CANCELLED, reply_markup=ReplyKeyboardRemove())


# ── Выбор вакансии → старт анкеты ────────────────────────────────────
@router.callback_query(F.data.startswith("vac:"))
async def vacancy_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    if await CandidateRepo(session).active_application(callback.from_user.id):
        await callback.message.answer(texts.ALREADY_APPLIED)
        return
    try:
        vacancy_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        return
    vacancy = await VacancyRepo(session).by_id(vacancy_id)
    if vacancy is None or vacancy.status != VacancyStatus.OPEN:
        await callback.message.answer(texts.NO_OPEN_VACANCIES)
        return

    data = await state.get_data()  # source из deep-link (handlers/common.py)
    await state.set_data(
        {
            "source": data.get("source"),
            "vacancy_id": vacancy.id,
            "is_cook": vacancy.position == Position.COOK,
            "tg_id": callback.from_user.id,
            "username": callback.from_user.username,
        }
    )
    await callback.message.answer(
        f"Вы выбрали: {texts.POSITION_LABELS[vacancy.position]} · "
        f"{escape(vacancy.branch.name)}"
    )
    await _ask_step(callback.message, state, "full_name")


# ── Кнопка «Назад» ───────────────────────────────────────────────────
async def _go_back_impl(
    message: Message, state: FSMContext, session: AsyncSession, current: str | None
) -> None:
    data = await state.get_data()
    steps = _build_steps(data.get("is_cook", False), data.get("is_male"))
    name = next((n for n in steps if _STEP_BY_NAME[n].state == current), None)
    if name is None:
        return
    idx = steps.index(name)
    if idx == 0:
        await state.set_state(None)
        vacancies = await VacancyRepo(session).open_vacancies()
        await message.answer(
            texts.CHOOSE_VACANCY, reply_markup=kb.vacancies_kb(vacancies)
        )
    else:
        await _ask_step(message, state, steps[idx - 1])


@router.callback_query(F.data == kb.BACK_CB)
async def go_back(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    await _go_back_impl(callback.message, state, session, await state.get_state())


# ── Шаги анкеты ──────────────────────────────────────────────────────
@router.message(Form.full_name, F.text)
async def step_name(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    name = validate_name(message.text)
    if name is None:
        await message.answer(texts.INVALID_NAME, reply_markup=kb.back_kb())
        return
    await state.update_data(full_name=name)
    await _goto_next(message, state, "full_name", session, bot)


@router.message(Form.age, F.text)
async def step_age(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    age = validate_age(message.text)
    if age is None:
        await message.answer(texts.INVALID_AGE, reply_markup=kb.back_kb())
        return
    await state.update_data(age=age)
    await _goto_next(message, state, "age", session, bot)


@router.callback_query(Form.gender, F.data.startswith("gender:"))
async def step_gender(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    try:
        gender = Gender(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.update_data(gender=gender.value, is_male=gender == Gender.MALE)
    await _goto_next(callback.message, state, "gender", session, bot)


@router.message(Form.gender)
async def gender_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.gender_kb())


@router.message(Form.phone, F.contact)
async def step_phone_contact(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await state.update_data(phone=phone)
    await message.answer("👍", reply_markup=ReplyKeyboardRemove())
    await _goto_next(message, state, "phone", session, bot)


@router.message(Form.phone, F.text)
async def step_phone_text(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    if message.text == texts.BTN_BACK:
        await message.answer("⬅️", reply_markup=ReplyKeyboardRemove())
        await _go_back_impl(message, state, session, Form.phone.state)
        return
    phone = validate_phone(message.text)
    if phone is None:
        await message.answer(texts.INVALID_PHONE, reply_markup=kb.phone_kb())
        return
    await state.update_data(phone=phone)
    await message.answer("👍", reply_markup=ReplyKeyboardRemove())
    await _goto_next(message, state, "phone", session, bot)


@router.callback_query(Form.district, F.data.startswith("district:"))
async def step_district(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    idx = parse_index(callback.data, len(texts.DISTRICTS))
    if idx is None:
        return
    await state.update_data(district=texts.DISTRICTS[idx])
    await _goto_next(callback.message, state, "district", session, bot)


@router.message(Form.district)
async def district_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.districts_kb())


@router.callback_query(Form.experience, F.data.startswith("exp:"))
async def step_experience(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    idx = parse_index(callback.data, len(texts.EXPERIENCE_OPTIONS))
    if idx is None:
        return
    await state.update_data(experience=texts.EXPERIENCE_OPTIONS[idx])
    await _goto_next(callback.message, state, "experience", session, bot)


@router.message(Form.experience)
async def experience_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.experience_kb())


@router.message(Form.cook_years, F.text)
async def step_cook_years(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    years = validate_int(message.text, 0, 50)
    if years is None:
        await message.answer(texts.INVALID_COOK_YEARS, reply_markup=kb.back_kb())
        return
    await state.update_data(cook_years=years)
    await _goto_next(message, state, "cook_years", session, bot)


@router.callback_query(Form.cook_spec, F.data.startswith("spec:"))
async def step_cook_spec(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    try:
        spec = CookSpec(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.update_data(cook_spec=spec.value)
    await _goto_next(callback.message, state, "cook_spec", session, bot)


@router.message(Form.cook_spec)
async def cook_spec_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.cook_spec_kb())


@router.callback_query(Form.russian, F.data.startswith("rus:"))
async def step_russian(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    try:
        lvl = RussianLevel(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.update_data(russian=lvl.value)
    await _goto_next(callback.message, state, "russian", session, bot)


@router.message(Form.russian)
async def russian_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.russian_kb())


@router.callback_query(Form.pork_alcohol, F.data.startswith("pork:"))
async def step_pork(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    await state.update_data(pork_alcohol_ok=callback.data.endswith(":yes"))
    await _goto_next(callback.message, state, "pork_alcohol", session, bot)


@router.message(Form.pork_alcohol)
async def pork_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.yes_no_kb("pork"))


@router.callback_query(Form.military, F.data.startswith("mil:"))
async def step_military(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    await state.update_data(military_id=callback.data.endswith(":yes"))
    await _goto_next(callback.message, state, "military", session, bot)


@router.message(Form.military)
async def military_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.yes_no_kb("mil"))


# ── Финал: скрининг и сохранение ─────────────────────────────────────
REQUIRED_FIELDS = {
    "vacancy_id", "tg_id", "full_name", "age", "gender", "phone",
    "district", "russian", "pork_alcohol_ok",
}


async def _finalize(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    await state.clear()
    if not REQUIRED_FIELDS.issubset(data):
        await message.answer(texts.FORM_EXPIRED)
        return

    vacancy = await VacancyRepo(session).by_id(data["vacancy_id"])
    if vacancy is None:
        await message.answer(texts.FORM_EXPIRED)
        return

    gender = Gender(data["gender"])
    result = await screen(
        session,
        ScreeningInput(
            position=vacancy.position,
            age=data["age"],
            gender=gender,
            russian=RussianLevel(data["russian"]),
            pork_alcohol_ok=data["pork_alcohol_ok"],
            military_id=data.get("military_id"),
            cook_years=data.get("cook_years"),
        ),
    )

    status = CandidateStatus.NEW if result.passed else CandidateStatus.SCREEN_REJECTED
    candidate = await CandidateRepo(session).create(
        tg_id=data["tg_id"],
        username=data.get("username"),
        full_name=data["full_name"],
        age=data["age"],
        gender=gender,
        phone=data["phone"],
        district=data["district"],
        experience_cat=data.get("experience", ""),
        cook_years=data.get("cook_years"),
        cook_spec=CookSpec(data["cook_spec"]) if data.get("cook_spec") else None,
        russian=RussianLevel(data["russian"]),
        pork_alcohol_ok=data["pork_alcohol_ok"],
        military_id=data.get("military_id"),
        vacancy_id=vacancy.id,
        status=status,
        rejection_reason=result.reason,
        source=data.get("source"),
    )

    if not result.passed:
        await message.answer(texts.SCREEN_REJECTED)
        logger.info("Кандидат #%s отклонён скринингом: %s", candidate.id, result.reason)
        return

    # адрес собеседования: повара — всегда Куйлюк, у шеф-повара
    if vacancy.position == Position.COOK:
        kuyluk = await get_cook_interview_branch(session)
        address = (
            f"{texts.COOK_INTERVIEW_NOTE}, {kuyluk.address}"
            if kuyluk
            else texts.COOK_INTERVIEW_NOTE
        )
    else:
        address = f"филиал {vacancy.branch.name}, {vacancy.branch.address}"

    await message.answer(
        texts.SCREEN_PASSED_TEMPLATE.format(
            position=texts.POSITION_LABELS[vacancy.position],
            branch=escape(vacancy.branch.name),
            salary=escape(vacancy.salary) or "—",
            schedule=escape(vacancy.schedule) or "—",
            description=(escape(vacancy.description) + "\n") if vacancy.description else "",
            interview_address=escape(address),
        ),
        reply_markup=kb.confirm_interview_kb(candidate.id),
    )


# ── Подтверждение собеседования ──────────────────────────────────────
@router.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        return
    answer, candidate_id = parts[1], int(parts[2])
    repo = CandidateRepo(session)
    candidate = await repo.by_id(candidate_id)
    if candidate is None or candidate.tg_id != callback.from_user.id:
        return
    if candidate.status != CandidateStatus.NEW:
        return  # уже обработано

    await callback.message.edit_reply_markup(reply_markup=None)
    if answer == "yes":
        await repo.change_status(candidate, CandidateStatus.INVITED)
        await callback.message.answer(texts.INVITED_OK)
        await send_invited_card(bot, session, candidate)
    else:
        await callback.message.answer(
            texts.DECLINE_OFFER_OTHER, reply_markup=kb.decline_offer_kb(candidate.id)
        )


@router.callback_query(F.data.startswith("declined:"))
async def cb_declined(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        return
    action, candidate_id = parts[1], int(parts[2])
    repo = CandidateRepo(session)
    candidate = await repo.by_id(candidate_id)
    if candidate is None or candidate.tg_id != callback.from_user.id:
        return
    if candidate.status == CandidateStatus.NEW:
        await repo.change_status(candidate, CandidateStatus.NOT_INTERESTED)

    if action == "other":
        vacancies = await VacancyRepo(session).open_vacancies()
        if not vacancies:
            await callback.message.answer(texts.NO_OPEN_VACANCIES)
            return
        await callback.message.answer(
            texts.CHOOSE_VACANCY, reply_markup=kb.vacancies_kb(vacancies)
        )
    else:
        await callback.message.answer(texts.NOT_INTERESTED_BYE)


# ── Устаревшие inline-кнопки ─────────────────────────────────────────
@router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer()
