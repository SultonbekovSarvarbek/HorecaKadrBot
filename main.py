"""Точка входа: сборка бота «Ченсон», запуск polling, graceful shutdown."""
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
from db.seed import seed_db
from handlers import (
    admin_users,
    candidate,
    common,
    maintenance,
    manager,
    recruiter_candidates,
    recruiter_vacancies,
    reports,
)
from middlewares import (
    AntiFloodMiddleware,
    DbSessionMiddleware,
    LoggingMiddleware,
    MaintenanceMiddleware,
)
from services.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


async def main() -> None:
    config = load_config()

    engine, session_factory = create_engine_and_session(config.database_url)
    await init_db(engine)
    await seed_db(session_factory, config)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config
    dp["session_factory"] = session_factory

    scheduler = AsyncIOScheduler(timezone=str(config.timezone))
    dp["scheduler"] = scheduler

    # ВАЖНО: outer_middleware — сессия БД нужна уже на этапе фильтров
    # (RoleFilter читает таблицу Users), а inner-middleware срабатывает
    # только после прохождения фильтров.
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(AntiFloodMiddleware(rate_limit=0.5))
        observer.outer_middleware(LoggingMiddleware())
        observer.outer_middleware(DbSessionMiddleware(session_factory))
        # после DbSession: заглушке нужна сессия, чтобы прочитать флаг
        observer.outer_middleware(MaintenanceMiddleware())

    # порядок: заглушка-команда владельца → ролевые роутеры →
    # /start → кандидат (его catch-all последним)
    dp.include_router(maintenance.router)
    dp.include_router(admin_users.router)
    dp.include_router(recruiter_vacancies.router)
    dp.include_router(recruiter_candidates.router)
    dp.include_router(reports.router)
    dp.include_router(manager.router)
    dp.include_router(common.router)
    dp.include_router(candidate.router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception(
            "Ошибка при обработке апдейта %s: %s",
            event.update.update_id,
            event.exception,
        )

    setup_scheduler(scheduler, bot, session_factory)
    scheduler.start()

    logger.info("Бот «Ченсон» запускается…")
    try:
        # не сбрасываем очередь: заявки за время даунтайма обработаются
        await bot.delete_webhook(drop_pending_updates=False)
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
