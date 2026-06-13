"""Админ: управление whitelist (Users), привязка чатов, настройки."""
import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

import texts
from config import DEFAULT_SETTINGS
from db.models import Role, User
from db.repository import AuditRepo, BranchRepo, SettingsRepo, UserRepo
from utils.roles import RoleFilter

logger = logging.getLogger("bot.admin")
router = Router(name="admin_users")
router.message.filter(RoleFilter(Role.ADMIN))


@router.message(Command("add_user"))
async def cmd_add_user(
    message: Message, command: CommandObject, session: AsyncSession, staff_user: User
) -> None:
    args = (command.args or "").split(maxsplit=2)
    if len(args) < 2 or not args[0].isdigit():
        await message.answer(texts.ADD_USER_USAGE)
        return
    tg_id = int(args[0])
    try:
        role = Role(args[1].strip().lower())
    except ValueError:
        await message.answer(texts.UNKNOWN_ROLE)
        return

    branch = None
    if role == Role.BRANCH_MANAGER:
        if len(args) < 3:
            await message.answer(texts.MANAGER_NEEDS_BRANCH)
            return
        branch = await BranchRepo(session).by_name(args[2])
        if branch is None:
            names = ", ".join(b.name for b in await BranchRepo(session).all())
            await message.answer(texts.UNKNOWN_BRANCH.format(branches=names))
            return

    repo = UserRepo(session)
    if await repo.by_tg(tg_id) is not None:
        await message.answer(texts.USER_EXISTS)
        return
    await repo.add(tg_id, role, branch_id=branch.id if branch else None)
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "user_added",
        f"tg={tg_id} role={role.value}" + (f" branch={branch.name}" if branch else ""),
    )
    await message.answer(
        texts.USER_ADDED.format(
            tg_id=tg_id,
            role=texts.ROLE_LABELS[role],
            branch=f", филиал {branch.name}" if branch else "",
        )
    )


@router.message(Command("users"))
async def cmd_users(message: Message, session: AsyncSession) -> None:
    users = await UserRepo(session).all()
    lines = [texts.USERS_TITLE]
    for u in users:
        branch = f" · {u.branch.name}" if u.branch else ""
        name = f" {escape(u.name)}" if u.name else ""
        lines.append(f"• <code>{u.tg_id}</code>{name} — {texts.ROLE_LABELS[u.role]}{branch}")
    await message.answer("\n".join(lines))


@router.message(Command("bind_chat"))
async def cmd_bind_chat(
    message: Message, command: CommandObject, session: AsyncSession, staff_user: User
) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer(texts.BIND_CHAT_USAGE)
        return
    if message.chat.type == "private":
        await message.answer(texts.BIND_CHAT_PRIVATE)
        return
    chat_id = message.chat.id
    if arg.lower() == "kitchen":
        await SettingsRepo(session).set("kitchen_chat_id", str(chat_id))
        await AuditRepo(session).log(
            staff_user.tg_id, staff_user.role.value, "bind_chat", f"kitchen={chat_id}"
        )
        await message.answer(texts.CHAT_BOUND_KITCHEN)
        return
    branch = await BranchRepo(session).by_name(arg)
    if branch is None:
        names = ", ".join(b.name for b in await BranchRepo(session).all())
        await message.answer(texts.UNKNOWN_BRANCH.format(branches=names))
        return
    await BranchRepo(session).set_chat(branch.id, chat_id)
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "bind_chat",
        f"branch={branch.name} chat={chat_id}",
    )
    await message.answer(texts.CHAT_BOUND_BRANCH.format(branch=escape(branch.name)))


@router.message(Command("set_setting"))
async def cmd_set_setting(
    message: Message, command: CommandObject, session: AsyncSession, staff_user: User
) -> None:
    args = (command.args or "").split(maxsplit=1)
    if len(args) != 2:
        await message.answer(
            texts.SET_SETTING_USAGE.format(keys=", ".join(DEFAULT_SETTINGS))
        )
        return
    key, value = args[0].strip(), args[1].strip()
    if key not in DEFAULT_SETTINGS:
        await message.answer(texts.UNKNOWN_SETTING)
        return
    # числовые пороги (дефолт-значение — число) обязаны быть числом,
    # иначе они молча игнорируются при чтении через get_int
    if DEFAULT_SETTINGS[key].isdigit() and not value.isdigit():
        await message.answer(texts.SETTING_NOT_NUMBER.format(key=key))
        return
    await SettingsRepo(session).set(key, value)
    await AuditRepo(session).log(
        staff_user.tg_id, staff_user.role.value, "setting_changed", f"{key}={value}"
    )
    await message.answer(texts.SETTING_SET.format(key=key, value=escape(value)))


@router.message(Command("settings"))
async def cmd_settings(message: Message, session: AsyncSession) -> None:
    merged = await SettingsRepo(session).all()
    lines = [texts.SETTINGS_TITLE]
    for key in DEFAULT_SETTINGS:
        lines.append(f"• <code>{key}</code> = {escape(merged.get(key, '')) or '—'}")
    await message.answer("\n".join(lines))
