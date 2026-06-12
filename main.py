"""Точка входа: сборка бота, запуск polling, graceful shutdown."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from db import create_engine_and_session, init_db
from handlers import admin, candidate
from middlewares import AntiFloodMiddleware, DbSessionMiddleware, LoggingMiddleware
from services.scheduler import restore_pending_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


async def main() -> None:
    config = load_config()

    engine, session_factory = create_engine_and_session(config.database_url)
    await init_db(engine)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # доступно в хендлерах по имени аргумента
    dp["config"] = config
    dp["session_factory"] = session_factory

    scheduler = AsyncIOScheduler(timezone=str(config.timezone))
    dp["scheduler"] = scheduler

    # middlewares (порядок: антифлуд → логирование → сессия БД)
    for observer in (dp.message, dp.callback_query):
        observer.middleware(AntiFloodMiddleware(rate_limit=0.5))
        observer.middleware(LoggingMiddleware())
        observer.middleware(DbSessionMiddleware(session_factory))

    # admin-роутер первым: его фильтр пропускает только админов,
    # остальные апдейты уходят в candidate-роутер
    dp.include_router(admin.router)
    dp.include_router(candidate.router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception(
            "Ошибка при обработке апдейта %s: %s",
            event.update.update_id,
            event.exception,
        )

    scheduler.start()
    await restore_pending_reminders(scheduler, bot, session_factory)

    logger.info("Бот запускается…")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Останавливаюсь…")
        scheduler.shutdown(wait=False)
        await engine.dispose()
        await bot.session.close()
        logger.info("Остановлен корректно.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Выход по сигналу.")
