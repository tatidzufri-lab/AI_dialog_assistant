import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards import booking_keyboard, cancel_keyboard, language_keyboard, remove_keyboard
from bot.texts import LANGS, TARIFF_LABELS, lang_from_telegram, lang_from_text, t
from config import Settings
from database import RetreatResultRepository
from schemas import RetreatSessionDraft
from services import AIRetreatService, RetreatService
from services.ai_retreat_prompts import TURN_INSTRUCTIONS
from services.retreat_service import NameTooShortError

logger = logging.getLogger(__name__)
router = Router()

# Язык каждого пользователя. Хранится в памяти, как и состояние диалога (MemoryStorage):
# после перезапуска бота язык снова берется из настроек Telegram.
_user_langs: dict[int, str] = {}


class RetreatStates(StatesGroup):
    active = State()


def get_lang(user_id: int | None, language_code: str | None) -> str:
    if user_id is not None and user_id in _user_langs:
        return _user_langs[user_id]
    return lang_from_telegram(language_code)


def set_lang(user_id: int | None, lang: str) -> None:
    if user_id is not None and lang in LANGS:
        _user_langs[user_id] = lang


def message_lang(message: Message) -> str:
    user = message.from_user
    return get_lang(user.id if user else None, user.language_code if user else None)


@router.message(CommandStart())
async def handle_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    settings: Settings,
    retreat_service: RetreatService,
) -> None:
    user_id = message.from_user.id if message.from_user else None
    # t.me/<бот>?start=en — ссылка с английской страницы сайта
    if command.args in LANGS:
        set_lang(user_id, command.args)
    lang = message_lang(message)
    set_lang(user_id, lang)

    await state.clear()
    await state.set_state(RetreatStates.active)
    await state.update_data(
        draft=retreat_service.start_session(settings.reflection_question_count).model_dump(),
        name_collected=False,
    )
    await message.answer(t("start", lang), reply_markup=cancel_keyboard(lang))


@router.message(Command("cancel"))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    lang = message_lang(message)
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(t("not_in_dialog", lang), reply_markup=remove_keyboard())
        return

    await state.clear()
    await message.answer(t("cancelled", lang), reply_markup=remove_keyboard())


@router.message(Command("language"))
async def handle_language(message: Message) -> None:
    await message.answer(t("choose_language", message_lang(message)), reply_markup=language_keyboard())


@router.message(Command("en", "ru"))
async def handle_language_shortcut(message: Message, command: CommandObject) -> None:
    set_lang(message.from_user.id if message.from_user else None, command.command)
    await message.answer(t("language_set", command.command))


@router.callback_query(F.data.startswith("lang:"))
async def handle_language_choice(callback: CallbackQuery) -> None:
    lang = (callback.data or "").split(":", 1)[-1]
    await callback.answer()
    if lang not in LANGS or callback.message is None:
        return
    set_lang(callback.from_user.id, lang)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t("language_set", lang))


@router.message(RetreatStates.active, F.text)
async def process_ai_retreat(
    message: Message,
    state: FSMContext,
    settings: Settings,
    retreat_service: RetreatService,
    ai_retreat_service: AIRetreatService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    state_data = await state.get_data()
    draft = RetreatSessionDraft.model_validate(state_data.get("draft", {}))
    name_collected = bool(state_data.get("name_collected"))
    user_text = message.text or ""
    user_id = message.from_user.id if message.from_user else None

    # Участница пишет на другом языке — проводница переходит на него.
    detected = lang_from_text(user_text)
    if detected:
        set_lang(user_id, detected)
    lang = message_lang(message)

    # Кризисные слова проверяются на обоих языках сразу.
    if name_collected and retreat_service.detect_crisis(user_text):
        logger.warning(
            "Crisis keywords detected for user_id=%s chat_id=%s",
            user_id or 0,
            message.chat.id,
        )
        draft_with_crisis = retreat_service.mark_crisis(draft)
        async with session_factory() as session:
            repository = RetreatResultRepository(session)
            await retreat_service.create_result(
                repository=repository,
                draft=draft_with_crisis,
                topic=settings.get_topic(lang),
                telegram_user_id=user_id or 0,
                telegram_chat_id=message.chat.id,
            )
        await state.clear()
        await message.answer(settings.get_crisis_response(lang), reply_markup=remove_keyboard())
        return

    try:
        if not name_collected:
            updated_draft = retreat_service.register_participant_name(
                draft=draft, participant_name=user_text
            )
            await state.update_data(draft=updated_draft.model_dump(), name_collected=True)
            ai_turn = await ai_retreat_service.generate_turn(
                draft=updated_draft,
                user_message=TURN_INSTRUCTIONS[lang]["named"].format(name=updated_draft.participant_name),
                is_new_dialogue=True,
                lang=lang,
            )
            updated_draft = retreat_service.apply_ai_turn(updated_draft, ai_turn)
            await state.update_data(draft=updated_draft.model_dump())
        else:
            ai_turn = await ai_retreat_service.generate_turn(
                draft=draft,
                user_message=user_text,
                is_new_dialogue=False,
                lang=lang,
            )
            updated_draft = retreat_service.apply_ai_turn(draft, ai_turn)
            await state.update_data(draft=updated_draft.model_dump())

        if ai_turn.phase == "completed":
            async with session_factory() as session:
                repository = RetreatResultRepository(session)
                await retreat_service.create_result(
                    repository=repository,
                    draft=updated_draft,
                    topic=settings.get_topic(lang),
                    telegram_user_id=user_id or 0,
                    telegram_chat_id=message.chat.id,
                )

            await state.clear()
            tariff_label = (
                TARIFF_LABELS[lang].get(updated_draft.recommended_tariff, "—")
                if updated_draft.recommended_tariff
                else "—"
            )
            await message.answer(ai_turn.reply, reply_markup=remove_keyboard())
            await message.answer(
                t("recommended", lang, tariff=tariff_label, booking=settings.get_booking_bot_display_name(lang)),
                reply_markup=booking_keyboard(
                    booking_bot_url=settings.get_booking_bot_url(lang),
                    dative_name=(
                        settings.booking_bot_dative_name if lang == "ru"
                        else settings.get_booking_bot_display_name("en")
                    ),
                    lang=lang,
                ),
            )
            return

        await message.answer(ai_turn.reply, reply_markup=cancel_keyboard(lang))
    except NameTooShortError:
        await message.answer(t("name_too_short", lang), reply_markup=cancel_keyboard(lang))
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=cancel_keyboard(lang))
    except Exception:
        logger.exception("Failed to process AI retreat turn")
        await message.answer(t("error", lang), reply_markup=cancel_keyboard(lang))


@router.message(RetreatStates.active)
async def handle_invalid_input(message: Message) -> None:
    lang = message_lang(message)
    await message.answer(t("text_only_in_dialog", lang), reply_markup=cancel_keyboard(lang))


@router.message(F.text)
async def handle_text_without_flow(message: Message) -> None:
    detected = lang_from_text(message.text or "")
    if detected and message.from_user:
        set_lang(message.from_user.id, detected)
    await message.answer(t("start_hint", message_lang(message)))


@router.message()
async def handle_unsupported_input(message: Message) -> None:
    await message.answer(t("text_only", message_lang(message)))
