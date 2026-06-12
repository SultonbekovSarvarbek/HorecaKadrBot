"""/start: определение роли по whitelist и показ нужного меню."""
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from db.models import Role
from db.repository import UserRepo
from handlers.candidate import show_candidate_menu
from keyboards.manager import manager_menu_kb

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    user = await UserRepo(session).by_tg(message.from_user.id)

    if user is None:
        # кандидат; сохраняем источник из deep-link (?start=hh и т.п.)
        source = (command.args or "").strip()[:64] or None
        if source:
            await state.update_data(source=source)
        await show_candidate_menu(message)
        return

    if user.role == Role.BRANCH_MANAGER:
        branch_name = user.branch.name if user.branch else "—"
        await message.answer(
            texts.MANAGER_MENU.format(branch=branch_name),
            reply_markup=manager_menu_kb(),
        )
    elif user.role == Role.CHEF:
        await message.answer(texts.CHEF_MENU, reply_markup=manager_menu_kb(chef=True))
    elif user.role == Role.RECRUITER:
        await message.answer(texts.RECRUITER_MENU)
    else:  # ADMIN
        await message.answer(texts.RECRUITER_MENU + texts.ADMIN_EXTRA_MENU)
