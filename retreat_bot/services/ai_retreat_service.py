import json
import logging
import re

import httpx

from config import Settings
from schemas import RetreatAssistantTurn, RetreatSessionDraft
from services.ai_retreat_prompts import (
    AI_RETREAT_RESPONSE_SCHEMA,
    TURN_INSTRUCTIONS,
    build_retreat_system_prompt,
    build_retreat_system_prompt_en,
)

SOFTER = {"ru": "[мягче]", "en": "[softer]"}

logger = logging.getLogger(__name__)


class AIRetreatService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._retreat_material = {lang: settings.get_retreat_material(lang) for lang in ("ru", "en")}
        self._audience_portraits = {lang: settings.get_audience_portraits(lang) for lang in ("ru", "en")}
        self._forbidden_words = {lang: settings.get_forbidden_words(lang) for lang in ("ru", "en")}
        self._forbidden_pattern = {
            lang: self._compile_forbidden_pattern(words) for lang, words in self._forbidden_words.items()
        }
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
        lang: str = "ru",
    ) -> RetreatAssistantTurn:
        payload = {
            "model": self._settings.openai_model,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(draft, lang),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        draft=draft,
                        user_message=user_message,
                        is_new_dialogue=is_new_dialogue,
                        lang=lang,
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
        return self._sanitize_turn(turn, lang)

    def _system_prompt(self, draft: RetreatSessionDraft, lang: str) -> str:
        s = self._settings
        if lang == "en":
            return build_retreat_system_prompt_en(
                topic=s.get_topic("en"),
                material=self._retreat_material["en"],
                audience_portraits=self._audience_portraits["en"],
                total_questions=draft.total_questions,
                forbidden_words=self._forbidden_words["en"],
                booking_bot_display_name=s.get_booking_bot_display_name("en"),
                booking_bot_username=s.booking_bot_username,
            )
        return build_retreat_system_prompt(
            topic=s.retreat_topic,
            material=self._retreat_material["ru"],
            audience_portraits=self._audience_portraits["ru"],
            total_questions=draft.total_questions,
            forbidden_words=self._forbidden_words["ru"],
            booking_bot_display_name=s.booking_bot_display_name,
            booking_bot_dative_name=s.booking_bot_dative_name,
            booking_bot_username=s.booking_bot_username,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _sanitize_turn(self, turn: RetreatAssistantTurn, lang: str = "ru") -> RetreatAssistantTurn:
        pattern = self._forbidden_pattern.get(lang)
        if pattern is None:
            return turn

        data = turn.model_dump()
        changed = False
        for key in ("reply", "next_question", "answer_feedback", "final_summary"):
            value = data.get(key)
            if isinstance(value, str) and pattern.search(value):
                cleaned = pattern.sub(SOFTER[lang], value)
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
        lang: str = "ru",
    ) -> str:
        ti = TURN_INSTRUCTIONS[lang]
        serialized_draft = json.dumps(draft.model_dump(), ensure_ascii=False, indent=2)
        remaining = max(draft.total_questions - draft.questions_answered, 0)
        progress_line = ti["progress"].format(a=draft.questions_answered, t=draft.total_questions, r=remaining)
        # Последний рефлексивный вопрос уже задан: этим ходом модель оценивает ответ
        # и сразу дает рекомендацию. Без этой строки она задавала шестой вопрос.
        last_answer = (
            draft.phase == "reflection"
            and draft.current_question
            and draft.questions_answered + 1 >= draft.total_questions
        )
        final_rule = f"\n\n{ti['final']}" if last_answer else ""
        return (
            f"{ti['new']}: {str(is_new_dialogue).lower()}\n"
            f"{ti['state']}:\n{serialized_draft}\n\n"
            f"{progress_line}\n\n"
            f"{ti['last']}:\n{user_message}\n\n"
            f"{ti['rules']}"
            f"{final_rule}"
        )
