import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.handlers import router
from bot.middlewares import LoggingMiddleware
from bot.texts import COMMANDS, DESCRIPTION_EN, SHORT_DESCRIPTION_EN
from config import get_settings
from database import create_engine, create_session_factory, init_db
from services import AIRetreatService, RetreatService

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    import logging.config

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": level.upper(),
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level.upper(),
            },
        }
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)


async def setup_bot_profile(bot: Bot) -> None:
    """Меню команд на двух языках и описание бота для англоязычных пользователей Telegram."""
    try:
        for lang, code in (("ru", None), ("ru", "ru"), ("ru", "uk"), ("en", "en")):
            await bot.set_my_commands(
                [BotCommand(command=c, description=d) for c, d in COMMANDS[lang]], language_code=code
            )
        await bot.set_my_description(DESCRIPTION_EN, language_code="en")
        await bot.set_my_short_description(SHORT_DESCRIPTION_EN, language_code="en")
    except Exception:
        logger.exception("Could not set bot commands/description")


async def run_bot() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    storage = MemoryStorage()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties())
    dp = Dispatcher(storage=storage)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    retreat_service = RetreatService(crisis_keywords=settings.get_crisis_keywords())
    ai_retreat_service = AIRetreatService(settings)

    await init_db(engine)

    dp.message.middleware(LoggingMiddleware())
    dp.include_router(router)
    dp["settings"] = settings
    dp["session_factory"] = session_factory
    dp["retreat_service"] = retreat_service
    dp["ai_retreat_service"] = ai_retreat_service

    await setup_bot_profile(bot)
    logger.info("Starting AI retreat bot")
    try:
        await dp.start_polling(bot)
    finally:
        await ai_retreat_service.close()
        await engine.dispose()
        await bot.session.close()
