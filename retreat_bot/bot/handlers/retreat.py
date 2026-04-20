import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards import booking_keyboard, cancel_keyboard, remove_keyboard
from config import Settings
from database import RetreatResultRepository
from schemas import TARIFF_LABELS, RetreatSessionDraft
from services import AIRetreatService, RetreatService

logger = logging.getLogger(__name__)
router = Router()


class RetreatStates(StatesGroup):
    active = State()


@router.message(Command("start"))
async def handle_start(
    message: Message,
    state: FSMContext,
    settings: Settings,
    retreat_service: RetreatService,
) -> None:
    await state.clear()
    await state.set_state(RetreatStates.active)
    await state.update_data(
        draft=retreat_service.start_session(settings.reflection_question_count).model_dump(),
        name_collected=False,
    )
    await message.answer(
        "Здравствуй. Рада, что ты заглянула в пространство ретрита «Познай себя».\n\n"
        "Я — твоя проводница в этом коротком разговоре. Мы не торопимся: "
        "я задам тебе несколько мягких вопросов, чтобы услышать, с чем ты пришла, "
        "и помочь выбрать формат, который откликнется именно тебе.\n\n"
        "Как мне к тебе обращаться?",
        reply_markup=cancel_keyboard(),
    )


@router.message(Command("cancel"))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "Сейчас мы с тобой не в диалоге. Когда будешь готова — напиши /start.",
            reply_markup=remove_keyboard(),
        )
        return

    await state.clear()
    await message.answer(
        "Спасибо, что заглянула. Пространство ретрита никуда не уходит — "
        "напиши /start, когда снова захочешь поговорить.",
        reply_markup=remove_keyboard(),
    )


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

    if name_collected and retreat_service.detect_crisis(user_text):
        logger.warning(
            "Crisis keywords detected for user_id=%s chat_id=%s",
            message.from_user.id if message.from_user else 0,
            message.chat.id,
        )
        draft_with_crisis = retreat_service.mark_crisis(draft)
        async with session_factory() as session:
            repository = RetreatResultRepository(session)
            await retreat_service.create_result(
                repository=repository,
                draft=draft_with_crisis,
                topic=settings.retreat_topic,
                telegram_user_id=message.from_user.id if message.from_user else 0,
                telegram_chat_id=message.chat.id,
            )
        await state.clear()
        await message.answer(settings.crisis_response, reply_markup=remove_keyboard())
        return

    try:
        if not name_collected:
            updated_draft = retreat_service.register_participant_name(
                draft=draft, participant_name=user_text
            )
            await state.update_data(draft=updated_draft.model_dump(), name_collected=True)
            ai_turn = await ai_retreat_service.generate_turn(
                draft=updated_draft,
                user_message=f"Участницу зовут {updated_draft.participant_name}. Она готова начать разговор.",
                is_new_dialogue=True,
            )
            updated_draft = retreat_service.apply_ai_turn(updated_draft, ai_turn)
            await state.update_data(draft=updated_draft.model_dump())
        else:
            ai_turn = await ai_retreat_service.generate_turn(
                draft=draft,
                user_message=user_text,
                is_new_dialogue=False,
            )
            updated_draft = retreat_service.apply_ai_turn(draft, ai_turn)
            await state.update_data(draft=updated_draft.model_dump())

        if ai_turn.phase == "completed":
            async with session_factory() as session:
                repository = RetreatResultRepository(session)
                await retreat_service.create_result(
                    repository=repository,
                    draft=updated_draft,
                    topic=settings.retreat_topic,
                    telegram_user_id=message.from_user.id if message.from_user else 0,
                    telegram_chat_id=message.chat.id,
                )

            await state.clear()
            tariff_label = (
                TARIFF_LABELS.get(updated_draft.recommended_tariff, "—")
                if updated_draft.recommended_tariff
                else "—"
            )
            await message.answer(ai_turn.reply, reply_markup=remove_keyboard())
            await message.answer(
                f"Рекомендованный формат: {tariff_label}.\n\n"
                f"Дальше тебя встретит {settings.booking_bot_display_name} — "
                f"нажми кнопку ниже, она расскажет про даты, свободные места "
                f"и забронирует их для тебя.",
                reply_markup=booking_keyboard(
                    booking_bot_url=settings.get_booking_bot_url(),
                    dative_name=settings.booking_bot_dative_name,
                ),
            )
            return

        await message.answer(ai_turn.reply, reply_markup=cancel_keyboard())
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=cancel_keyboard())
    except Exception:
        logger.exception("Failed to process AI retreat turn")
        await message.answer(
            "Что-то прервалось на моей стороне. Давай попробуем ещё раз — "
            "напиши своё сообщение снова или отправь /cancel.",
            reply_markup=cancel_keyboard(),
        )


@router.message(RetreatStates.active)
async def handle_invalid_input(message: Message) -> None:
    await message.answer(
        "Давай останемся в словах — отправь, пожалуйста, текстовое сообщение.",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text)
async def handle_text_without_flow(message: Message) -> None:
    await message.answer(
        "Чтобы начать разговор о ретрите «Познай себя», отправь /start."
    )


@router.message()
async def handle_unsupported_input(message: Message) -> None:
    await message.answer(
        "Я умею разговаривать только текстом. Отправь /start, чтобы начать."
    )
