"""Воронка кандидата: /start (с deep-link source) и FSM-анкета."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from config import Config
from db.models import CandidateStatus, Vacancy
from db.repository import CandidateRepository
from keyboards import candidate as kb
from services.notifications import notify_admins_new_application
from utils.validators import validate_age, validate_name, validate_phone

logger = logging.getLogger("bot.candidate")
router = Router(name="candidate")


class Form(StatesGroup):
    name = State()
    age = State()
    phone = State()
    district = State()
    experience = State()
    schedule = State()
    start_when = State()


# Порядок шагов для кнопки «Назад»
STEP_ORDER = [
    Form.name,
    Form.age,
    Form.phone,
    Form.district,
    Form.experience,
    Form.schedule,
    Form.start_when,
]


async def _ask_step(message: Message, state: FSMContext, step: State) -> None:
    """Задаёт вопрос текущего шага с нужной клавиатурой."""
    await state.set_state(step)
    if step == Form.name:
        await message.answer(texts.ASK_NAME, reply_markup=kb.back_kb())
    elif step == Form.age:
        await message.answer(texts.ASK_AGE, reply_markup=kb.back_kb())
    elif step == Form.phone:
        await message.answer(texts.ASK_PHONE, reply_markup=kb.phone_kb())
    elif step == Form.district:
        await message.answer(texts.ASK_DISTRICT, reply_markup=kb.districts_kb())
    elif step == Form.experience:
        await message.answer(texts.ASK_EXPERIENCE, reply_markup=kb.experience_kb())
    elif step == Form.schedule:
        await message.answer(texts.ASK_SCHEDULE, reply_markup=kb.schedule_kb())
    elif step == Form.start_when:
        await message.answer(texts.ASK_START_WHEN, reply_markup=kb.start_when_kb())


# ── /start ───────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    repo = CandidateRepository(session)
    active = await repo.get_active_application(message.from_user.id)
    if active is not None:
        await message.answer(texts.ALREADY_APPLIED)
        return

    source = (command.args or "").strip()[:64] or None
    await state.update_data(source=source)
    await message.answer(texts.WELCOME, reply_markup=kb.vacancies_kb())


@router.message(Command("admin"))
async def admin_denied(message: Message) -> None:
    # сюда попадают только не-админы: admin-роутер подключён раньше
    await message.answer(texts.ADMIN_ONLY)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer(texts.FORM_CANCELLED, reply_markup=ReplyKeyboardRemove())


# ── Выбор вакансии ───────────────────────────────────────────────────
@router.callback_query(F.data.startswith("vacancy:"))
async def vacancy_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    repo = CandidateRepository(session)
    active = await repo.get_active_application(callback.from_user.id)
    if active is not None:
        await callback.answer()
        await callback.message.edit_text(texts.ALREADY_APPLIED)
        return

    vacancy = Vacancy(callback.data.split(":", 1)[1])
    await state.update_data(vacancy=vacancy.value)
    await callback.answer()
    await callback.message.edit_text(
        f"Вы выбрали: {texts.VACANCY_LABELS[vacancy]}"
    )
    await _ask_step(callback.message, state, Form.name)


# ── Кнопка «Назад» ───────────────────────────────────────────────────
@router.callback_query(F.data == kb.BACK_CB)
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    await callback.answer()
    idx = next(
        (i for i, s in enumerate(STEP_ORDER) if s.state == current), None
    )
    if idx is None:
        return
    if idx == 0:
        # с первого шага — назад к выбору вакансии
        await state.set_state(None)
        await callback.message.answer(texts.WELCOME, reply_markup=kb.vacancies_kb())
    else:
        await _ask_step(callback.message, state, STEP_ORDER[idx - 1])


# ── Шаг 1: имя ───────────────────────────────────────────────────────
@router.message(Form.name, F.text)
async def step_name(message: Message, state: FSMContext) -> None:
    name = validate_name(message.text)
    if name is None:
        await message.answer(texts.INVALID_NAME, reply_markup=kb.back_kb())
        return
    await state.update_data(name=name)
    await _ask_step(message, state, Form.age)


# ── Шаг 2: возраст ───────────────────────────────────────────────────
@router.message(Form.age, F.text)
async def step_age(message: Message, state: FSMContext) -> None:
    age = validate_age(message.text)
    if age is None:
        await message.answer(texts.INVALID_AGE, reply_markup=kb.back_kb())
        return
    await state.update_data(age=age)
    await _ask_step(message, state, Form.phone)


# ── Шаг 3: телефон (контакт или вручную) ─────────────────────────────
@router.message(Form.phone, F.contact)
async def step_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await state.update_data(phone=phone)
    await message.answer("👍", reply_markup=ReplyKeyboardRemove())
    await _ask_step(message, state, Form.district)


@router.message(Form.phone, F.text)
async def step_phone_text(message: Message, state: FSMContext) -> None:
    if message.text == texts.BTN_BACK:
        await message.answer("⬅️", reply_markup=ReplyKeyboardRemove())
        await _ask_step(message, state, Form.age)
        return
    phone = validate_phone(message.text)
    if phone is None:
        await message.answer(texts.INVALID_PHONE, reply_markup=kb.phone_kb())
        return
    await state.update_data(phone=phone)
    await message.answer("👍", reply_markup=ReplyKeyboardRemove())
    await _ask_step(message, state, Form.district)


# ── Шаг 4: район ─────────────────────────────────────────────────────
@router.callback_query(Form.district, F.data.startswith("district:"))
async def step_district(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":", 1)[1])
    if not 0 <= idx < len(texts.DISTRICTS):
        await callback.answer()
        return
    await state.update_data(district=texts.DISTRICTS[idx])
    await callback.answer()
    await _ask_step(callback.message, state, Form.experience)


@router.message(Form.district)
async def district_text_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.districts_kb())


# ── Шаг 5: опыт ──────────────────────────────────────────────────────
@router.callback_query(Form.experience, F.data.startswith("exp:"))
async def step_experience(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":", 1)[1])
    if not 0 <= idx < len(texts.EXPERIENCE_OPTIONS):
        await callback.answer()
        return
    await state.update_data(experience=texts.EXPERIENCE_OPTIONS[idx])
    await callback.answer()
    await _ask_step(callback.message, state, Form.schedule)


@router.message(Form.experience)
async def experience_text_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.experience_kb())


# ── Шаг 6: график ────────────────────────────────────────────────────
@router.callback_query(Form.schedule, F.data.startswith("schedule:"))
async def step_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    schedule_ok = callback.data.split(":", 1)[1] == "yes"
    await state.update_data(schedule_ok=schedule_ok)
    await callback.answer()
    await _ask_step(callback.message, state, Form.start_when)


@router.message(Form.schedule)
async def schedule_text_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.schedule_kb())


# ── Шаг 7: когда готов выйти + финал ─────────────────────────────────
@router.callback_query(Form.start_when, F.data.startswith("when:"))
async def step_start_when(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    config: Config,
) -> None:
    idx = int(callback.data.split(":", 1)[1])
    if not 0 <= idx < len(texts.START_WHEN_OPTIONS):
        await callback.answer()
        return
    await callback.answer()
    data = await state.get_data()
    await state.clear()

    # Авто-скрининг: младше 18 или не готов к графику → отказ
    passed = data["age"] >= 18 and data["schedule_ok"]
    status = CandidateStatus.NEW if passed else CandidateStatus.REJECTED

    repo = CandidateRepository(session)
    candidate = await repo.create_candidate(
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        name=data["name"],
        age=data["age"],
        phone=data["phone"],
        district=data["district"],
        vacancy=Vacancy(data["vacancy"]),
        experience=data["experience"],
        schedule_ok=data["schedule_ok"],
        start_when=texts.START_WHEN_OPTIONS[idx],
        status=status,
        source=data.get("source"),
    )

    if passed:
        await callback.message.edit_text(texts.APPLICATION_ACCEPTED)
        await notify_admins_new_application(bot, config.admin_ids, candidate)
    else:
        await callback.message.edit_text(texts.APPLICATION_REJECTED)
        logger.info("Кандидат #%s отклонён авто-скринингом", candidate.id)


@router.message(Form.start_when)
async def start_when_text_fallback(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS, reply_markup=kb.start_when_kb())
