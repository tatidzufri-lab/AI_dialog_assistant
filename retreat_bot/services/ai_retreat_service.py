import json
import logging
import re

import httpx

from config import Settings
from schemas import RetreatAssistantTurn, RetreatSessionDraft
from services.ai_retreat_prompts import (
    AI_RETREAT_RESPONSE_SCHEMA,
    build_retreat_system_prompt,
)

logger = logging.getLogger(__name__)


class AIRetreatService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._retreat_material = settings.get_retreat_material()
        self._audience_portraits = settings.get_audience_portraits()
        self._forbidden_words = settings.get_forbidden_words()
        self._forbidden_pattern = self._compile_forbidden_pattern(self._forbidden_words)
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(120.0, connect=30.0),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate_turn(
        self,
        draft: RetreatSessionDraft,
        user_message: str,
        is_new_dialogue: bool,
    ) -> RetreatAssistantTurn:
        payload = {
            "model": self._settings.openai_model,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "system",
                    "content": build_retreat_system_prompt(
                        topic=self._settings.retreat_topic,
                        material=self._retreat_material,
                        audience_portraits=self._audience_portraits,
                        total_questions=draft.total_questions,
                        forbidden_words=self._forbidden_words,
                        booking_bot_display_name=self._settings.booking_bot_display_name,
                        booking_bot_dative_name=self._settings.booking_bot_dative_name,
                        booking_bot_username=self._settings.booking_bot_username,
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        draft=draft,
                        user_message=user_message,
                        is_new_dialogue=is_new_dialogue,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": AI_RETREAT_RESPONSE_SCHEMA,
            },
        }

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        turn = RetreatAssistantTurn.model_validate(json.loads(content))
        return self._sanitize_turn(turn)

    async def close(self) -> None:
        await self._client.aclose()

    def _sanitize_turn(self, turn: RetreatAssistantTurn) -> RetreatAssistantTurn:
        if self._forbidden_pattern is None:
            return turn

        data = turn.model_dump()
        changed = False
        for key in ("reply", "next_question", "answer_feedback", "final_summary"):
            value = data.get(key)
            if isinstance(value, str) and self._forbidden_pattern.search(value):
                cleaned = self._forbidden_pattern.sub("[мягче]", value)
                logger.warning(
                    "AI reply contained forbidden wording in field '%s'; sanitized.", key
                )
                data[key] = cleaned
                changed = True

        if not changed:
            return turn
        return RetreatAssistantTurn.model_validate(data)

    @staticmethod
    def _compile_forbidden_pattern(words: list[str]) -> re.Pattern[str] | None:
        if not words:
            return None
        alternatives = [re.escape(w) for w in words if w]
        if not alternatives:
            return None
        pattern = r"(?i)(" + "|".join(alternatives) + r")"
        return re.compile(pattern)

    @staticmethod
    def _build_prompt(
        draft: RetreatSessionDraft,
        user_message: str,
        is_new_dialogue: bool,
    ) -> str:
        serialized_draft = json.dumps(draft.model_dump(), ensure_ascii=False, indent=2)
        remaining = max(draft.total_questions - draft.questions_answered, 0)
        progress_line = (
            f"Прогресс reflection: {draft.questions_answered}/{draft.total_questions} "
            f"(осталось {remaining})."
        )
        return (
            f"Новая сессия: {str(is_new_dialogue).lower()}\n"
            f"Текущее состояние сессии:\n{serialized_draft}\n\n"
            f"{progress_line}\n\n"
            f"Последнее сообщение участницы:\n{user_message}\n\n"
            "ОБЯЗАТЕЛЬНО на этом ходу:\n"
            "- если phase=discovery и это уже второе сообщение участницы — на этом ходу "
            "ставь phase=reflection и сразу задавай первый рефлексивный вопрос;\n"
            "- если phase=reflection — оцени ответ участницы (latest_answer_evaluated=true, "
            "answer_feedback) И сразу задай следующий рефлексивный вопрос (next_question), "
            "это один и тот же ход;\n"
            "- если questions_answered уже == total_questions — переходи в recommendation, "
            "выбирай тариф и заполняй final_summary;\n"
            "- если phase=recommendation и участница подтвердила интерес "
            "(«да», «хочу», «откликается», «давай», вопрос про даты) — phase=completed "
            "с тёплым прощанием и упоминанием передачи;\n"
            "- НИКОГДА не возвращай ответ без next_question в reflection (кроме перехода "
            "в recommendation). Не задавай уточняющий вопрос вместо нового рефлексивного."
        )
