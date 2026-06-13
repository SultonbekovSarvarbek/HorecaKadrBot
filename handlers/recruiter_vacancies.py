"""Рекрутер/админ: управление вакансиями и обработка заявок на персонал."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import Position, Role, StaffRequestStatus, User
from db.repository import (
    AuditRepo,
    BranchRepo,
    SettingsRepo,
    StaffRequestRepo,
    VacancyRepo,
)
from keyboards.recruiter import branches_kb, positions_kb, vacancies_pick_kb
from utils.roles import RoleFilter
from utils.validators import validate_int

logger = logging.getLogger("bot.recruiter.vacancies")
router = Router(name="recruiter_vacancies")
router.message.filter(RoleFilter(Role.RECRUITER, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.RECRUITER, Role.ADMIN))


class VacancyForm(StatesGroup):
    branch = State()
    position = State()
    salary = State()
    schedule = State()
    description = State()
    quota = State()


class ClarifyForm(StatesGroup):
    text = State()


class QuotaForm(StatesGroup):
    value = State()


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer(texts.ACTION_CANCELLED)


# ── /vacancies ───────────────────────────────────────────────────────
@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message, session: AsyncSession) -> None:
    repo = VacancyRepo(session)
    vacancies = await repo.all_vacancies()
    if not vacancies:
        await message.answer(texts.VAC_EMPTY)
        return
    hired = await repo.hired_counts([v.id for v in vacancies])
    lines = [texts.VAC_LIST_TITLE]
    for v in vacancies:
        lines.append(
            texts.VAC_LINE.format(
                id=v.id,
                position=texts.POSITION_LABELS[v.position],
                branch=escape(v.branch.name),
                status=texts.VACANCY_STATUS_LABELS[v.status],
                hired=hired.get(v.id, 0),
                quota=v.quota,
            )
        )
    await message.answer("\n".join(lines))


# ── /add_vacancy (вручную или из заявки менеджера) ───────────────────
@router.message(Command("add_vacancy"))
async def cmd_add_vacancy(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    branches = await BranchRepo(session).all()
    await state.set_state(VacancyForm.branch)
    await message.answer(texts.VAC_ASK_BRANCH, reply_markup=branches_kb(branches, "vbr"))


@router.callback_query(VacancyForm.branch, F.data.startswith("vbr:"))
async def vac_branch(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    raw = callback.data.split(":", 1)[1]
    if not raw.isdigit():
        return
    await state.update_data(branch_id=int(raw))
    await state.set_state(VacancyForm.position)
    await callback.message.answer(texts.VAC_ASK_POSITION, reply_markup=positions_kb("vpos"))


@router.callback_query(VacancyForm.position, F.data.startswith("vpos:"))
async def vac_position(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        position = Position(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.update_data(position=position.value)
    await state.set_state(VacancyForm.salary)
    await callback.message.answer(texts.VAC_ASK_SALARY)


@router.message(VacancyForm.salary, F.text)
async def vac_salary(message: Message, state: FSMContext) -> None:
    await state.update_data(salary=message.text.strip()[:128])
    await state.set_state(VacancyForm.schedule)
    await message.answer(texts.VAC_ASK_SCHEDULE)


@router.message(VacancyForm.schedule, F.text)
async def vac_schedule(message: Message, state: FSMContext) -> None:
    await state.update_data(schedule=message.text.strip()[:128])
    await state.set_state(VacancyForm.description)
    await message.answer(texts.VAC_ASK_DESCRIPTION)


@router.message(VacancyForm.description, F.text)
async def vac_description(message: Message, state: FSMContext) -> None:
    description = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=description)
    await state.set_state(VacancyForm.quota)
    await message.answer(texts.VAC_ASK_QUOTA)


@router.message(VacancyForm.quota, F.text)
async def vac_quota(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    staff_user: User,
) -> None:
    quota = validate_int(message.text, 1, 100)
    if quota is None:
        await message.answer(texts.VAC_INVALID_QUOTA)
        return
    data = await state.get_data()
    await state.clear()
    if "branch_id" not in data or "position" not in data:
        await message.answer(texts.FORM_EXPIRED)
        return

    vacancy = await VacancyRepo(session).create(
        branch_id=data["branch_id"],
        position=Position(data["position"]),
        salary=data.get("salary", ""),
        schedule=data.get("schedule", ""),
        description=data.get("description", ""),
        quota=quota,
    )
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "vacancy_created",
        f"vac={vacancy.id} {vacancy.position.value} branch={vacancy.branch_id}",
    )
    await message.answer(
        texts.VAC_CREATED.format(
            id=vacancy.id,
            position=texts.POSITION_LABELS[vacancy.position],
            branch=escape(vacancy.branch.name),
        )
    )

    # если вакансия создана из заявки менеджера — закрываем заявку и сообщаем
    request_id = data.get("staff_request_id")
    if request_id:
        sr_repo = StaffRequestRepo(session)
        req = await sr_repo.by_id(request_id)
        if req is not None:
            await sr_repo.set_status(req, StaffRequestStatus.CONVERTED)
            try:
                await bot.send_message(
                    req.manager_tg_id,
                    f"✅ По вашей заявке №{req.id} создана вакансия #{vacancy.id}.",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Менеджер %s недоступен: %s", req.manager_tg_id, e)


# ── Обработка заявки менеджера ───────────────────────────────────────
@router.callback_query(F.data.startswith("sr:create:"))
async def sr_create_vacancy(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    raw = callback.data.split(":")[2]
    if not raw.isdigit():
        return
    repo = StaffRequestRepo(session)
    req = await repo.by_id(int(raw))
    if req is None:
        return
    if req.status not in (StaffRequestStatus.NEW, StaffRequestStatus.IN_PROGRESS):
        await callback.message.answer(texts.SR_ALREADY_PROCESSED)
        return
    await repo.set_status(req, StaffRequestStatus.IN_PROGRESS)
    # префилл из заявки: филиал, позиция, квота = количеству
    await state.clear()
    await state.set_state(VacancyForm.salary)
    await state.update_data(
        branch_id=req.branch_id,
        position=req.position.value,
        staff_request_id=req.id,
    )
    await callback.message.answer(
        f"Создание вакансии из заявки №{req.id}: "
        f"{texts.POSITION_LABELS[req.position]} · {escape(req.branch.name)}\n\n"
        + texts.VAC_ASK_SALARY
    )


@router.callback_query(F.data.startswith("sr:clarify:"))
async def sr_clarify_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    raw = callback.data.split(":")[2]
    if not raw.isdigit():
        return
    await state.clear()
    await state.set_state(ClarifyForm.text)
    await state.update_data(staff_request_id=int(raw))
    await callback.message.answer(texts.SR_CLARIFY_ASK)


@router.message(ClarifyForm.text, F.text)
async def sr_clarify_send(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    await state.clear()
    req = await StaffRequestRepo(session).by_id(data.get("staff_request_id", 0))
    if req is None:
        await message.answer(texts.FORM_EXPIRED)
        return
    try:
        await bot.send_message(
            req.manager_tg_id,
            texts.SR_CLARIFY_FOR_MANAGER.format(id=req.id, text=escape(message.text)),
        )
        await message.answer(texts.SR_CLARIFY_SENT)
    except Exception as e:  # noqa: BLE001
        logger.warning("Менеджер %s недоступен: %s", req.manager_tg_id, e)
        await message.answer("⚠️ Не удалось отправить менеджеру.")


@router.callback_query(F.data.startswith("sr:reject:"))
async def sr_reject(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, staff_user: User
) -> None:
    await callback.answer()
    raw = callback.data.split(":")[2]
    if not raw.isdigit():
        return
    repo = StaffRequestRepo(session)
    req = await repo.by_id(int(raw))
    if req is None:
        return
    if req.status == StaffRequestStatus.CONVERTED:
        await callback.message.answer(texts.SR_ALREADY_PROCESSED)
        return
    await repo.set_status(req, StaffRequestStatus.REJECTED)
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "staff_request_rejected", f"req={req.id}"
    )
    await callback.message.answer(f"Заявка №{req.id} отклонена.")
    try:
        await bot.send_message(
            req.manager_tg_id, texts.SR_REJECTED_FOR_MANAGER.format(id=req.id)
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Менеджер %s недоступен: %s", req.manager_tg_id, e)


# ── /close_vacancy и /set_quota ──────────────────────────────────────
@router.message(Command("close_vacancy"))
async def cmd_close_vacancy(message: Message, session: AsyncSession) -> None:
    vacancies = await VacancyRepo(session).open_vacancies()
    if not vacancies:
        await message.answer(texts.VAC_EMPTY)
        return
    await message.answer(
        texts.VAC_CHOOSE_TO_CLOSE, reply_markup=vacancies_pick_kb(vacancies, "vclose")
    )


@router.callback_query(F.data.startswith("vclose:"))
async def cb_close_vacancy(
    callback: CallbackQuery, session: AsyncSession, staff_user: User
) -> None:
    await callback.answer()
    raw = callback.data.split(":", 1)[1]
    if not raw.isdigit():
        return
    vacancy = await VacancyRepo(session).close(int(raw))
    if vacancy is None:
        return
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "vacancy_closed", f"vac={vacancy.id}"
    )
    await callback.message.answer(texts.VAC_CLOSED.format(id=vacancy.id))


@router.message(Command("set_quota"))
async def cmd_set_quota(message: Message, session: AsyncSession) -> None:
    vacancies = await VacancyRepo(session).open_vacancies()
    if not vacancies:
        await message.answer(texts.VAC_EMPTY)
        return
    await message.answer(
        texts.VAC_CHOOSE_FOR_QUOTA, reply_markup=vacancies_pick_kb(vacancies, "vquota")
    )


@router.callback_query(F.data.startswith("vquota:"))
async def cb_quota_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    raw = callback.data.split(":", 1)[1]
    if not raw.isdigit():
        return
    await state.set_state(QuotaForm.value)
    await state.update_data(vacancy_id=int(raw))
    await callback.message.answer(texts.VAC_ASK_NEW_QUOTA.format(id=raw))


@router.message(QuotaForm.value, F.text)
async def cb_quota_set(
    message: Message, state: FSMContext, session: AsyncSession, staff_user: User
) -> None:
    quota = validate_int(message.text, 1, 100)
    if quota is None:
        await message.answer(texts.VAC_INVALID_QUOTA)
        return
    data = await state.get_data()
    await state.clear()
    vacancy = await VacancyRepo(session).set_quota(data.get("vacancy_id", 0), quota)
    if vacancy is None:
        await message.answer(texts.FORM_EXPIRED)
        return
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "quota_set",
        f"vac={vacancy.id} quota={quota}",
    )
    await message.answer(texts.VAC_QUOTA_SET.format(id=vacancy.id, quota=quota))


# ── /templates ───────────────────────────────────────────────────────
@router.message(Command("templates"))
async def cmd_templates(message: Message, session: AsyncSession, bot: Bot) -> None:
    vacancies = await VacancyRepo(session).open_vacancies()
    if not vacancies:
        await message.answer(texts.VAC_EMPTY)
        return
    me = await bot.get_me()
    blocks = [texts.TEMPLATES_TITLE]
    for v in vacancies:
        blocks.append(
            texts.TEMPLATE_VACANCY.format(
                position=texts.POSITION_LABELS[v.position],
                branch=escape(v.branch.name),
                address=escape(v.branch.address),
                salary=escape(v.salary) or "—",
                schedule=escape(v.schedule) or "—",
                description=escape(v.description),
                bot_username=me.username,
            )
        )
    drive = await SettingsRepo(session).get("drive_link")
    blocks.append(
        texts.TEMPLATES_DRIVE.format(link=drive) if drive else texts.TEMPLATES_NO_DRIVE
    )
    await message.answer("\n\n".join(blocks), disable_web_page_preview=True)
