"""Ручная рассылка админам с сервера (например, о приостановке сервиса).

Запуск независим от основного бота — работает, даже когда бот остановлен
на обслуживание. Берёт получателей из двух источников и объединяет их:
  • роль ADMIN в таблице Users;
  • ADMIN_IDS из .env (чтобы владелец получил даже без записи в whitelist).

Использование:
    python notify_admins.py                       # дефолтный текст «сервис на обслуживании»
    python notify_admins.py "Свой текст сообщения" # произвольный текст
    python notify_admins.py --up                   # «сервис снова в строю»
"""
import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_config
from db import Role, create_engine_and_session
from db.repository import UserRepo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("notify_admins")

DEFAULT_DOWN = (
    "🛠 <b>Технические работы</b>\n\n"
    "Бот приостанавливает сервис на время обслуживания. "
    "Заявки за это время не теряются — они обработаются после возобновления."
)
DEFAULT_UP = (
    "✅ <b>Сервис восстановлен</b>\n\n"
    "Бот снова в строю. Все заявки, поступившие во время обслуживания, обработаны."
)


def _build_text(argv: list[str]) -> str:
    args = argv[1:]
    if args and args[0] in ("--up", "-u"):
        return DEFAULT_UP
    custom = " ".join(args).strip()
    return custom or DEFAULT_DOWN


async def _recipients(config, session_factory) -> set[int]:
    """ADMIN из БД ∪ ADMIN_IDS из .env."""
    ids: set[int] = set(config.admin_ids)
    async with session_factory() as session:
        for u in await UserRepo(session).by_role(Role.ADMIN):
            ids.add(u.tg_id)
    return ids


async def main() -> None:
    text = _build_text(sys.argv)
    config = load_config()
    engine, session_factory = create_engine_and_session(config.database_url)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        recipients = await _recipients(config, session_factory)
        if not recipients:
            logger.warning("Нет получателей — рассылка не выполнена.")
            return

        sent, failed = 0, 0
        for chat_id in recipients:
            try:
                await bot.send_message(chat_id, text)
                sent += 1
            except Exception as e:  # noqa: BLE001 — недоступный чат не должен ломать рассылку
                failed += 1
                logger.warning("Не доставлено %s: %s", chat_id, e)
        logger.info("Готово: доставлено %d, ошибок %d (из %d).", sent, failed, len(recipients))
    finally:
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
