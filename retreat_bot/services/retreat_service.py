import re

from database.models import RetreatResult
from database.repository import RetreatResultRepository
from schemas import (
    RetreatAssistantTurn,
    RetreatResultCreate,
    RetreatSessionDraft,
)


class RetreatService:
    def __init__(self, crisis_keywords: list[str]) -> None:
        self._crisis_keywords = [w.lower() for w in crisis_keywords if w]
        if self._crisis_keywords:
            pattern = r"(?i)(" + "|".join(re.escape(w) for w in self._crisis_keywords) + r")"
            self._crisis_pattern: re.Pattern[str] | None = re.compile(pattern)
        else:
            self._crisis_pattern = None

    @staticmethod
    def validate_participant_name(value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if len(cleaned) < 2:
            raise ValueError("Пожалуйста, напиши имя хотя бы из двух символов.")
        return cleaned

    def start_session(self, total_questions: int) -> RetreatSessionDraft:
        return RetreatSessionDraft(total_questions=total_questions)

    def register_participant_name(
        self,
        draft: RetreatSessionDraft,
        participant_name: str,
    ) -> RetreatSessionDraft:
        updated = RetreatSessionDraft.model_validate(draft.model_dump())
        updated.participant_name = self.validate_participant_name(participant_name)
        updated.phase = "discovery"
        return updated

    def detect_crisis(self, text: str) -> bool:
        if not text or self._crisis_pattern is None:
            return False
        return bool(self._crisis_pattern.search(text))

    def mark_crisis(self, draft: RetreatSessionDraft) -> RetreatSessionDraft:
        updated = RetreatSessionDraft.model_validate(draft.model_dump())
        updated.crisis_detected = True
        return updated

    def apply_ai_turn(
        self,
        current: RetreatSessionDraft,
        ai_turn: RetreatAssistantTurn,
    ) -> RetreatSessionDraft:
        updated = RetreatSessionDraft.model_validate(current.model_dump())
        updated.phase = ai_turn.phase

        if (
            ai_turn.latest_answer_evaluated
            and current.phase == "reflection"
            and current.current_question
        ):
            updated.questions_answered = min(
                updated.questions_answered + 1, updated.total_questions
            )

        if ai_turn.answer_feedback is not None:
            updated.last_answer_feedback = ai_turn.answer_feedback

        updated.current_question = ai_turn.next_question

        if ai_turn.audience_segment is not None:
            updated.audience_segment = ai_turn.audience_segment

        if ai_turn.recommended_tariff is not None:
            updated.recommended_tariff = ai_turn.recommended_tariff

        if ai_turn.new_readiness_signals:
            existing = set(updated.readiness_signals)
            for signal in ai_turn.new_readiness_signals:
                cleaned = " ".join(signal.split()).strip()
                if cleaned and cleaned not in existing:
                    updated.readiness_signals.append(cleaned)
                    existing.add(cleaned)

        if ai_turn.final_summary is not None:
            updated.final_summary = ai_turn.final_summary

        return updated

    async def create_result(
        self,
        repository: RetreatResultRepository,
        draft: RetreatSessionDraft,
        topic: str,
        telegram_user_id: int,
        telegram_chat_id: int,
    ) -> RetreatResult:
        readiness_signals_text = (
            "; ".join(draft.readiness_signals) if draft.readiness_signals else None
        )
        result_in = RetreatResultCreate(
            participant_name=draft.participant_name or "Неизвестная участница",
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            topic=topic,
            total_questions=draft.total_questions,
            questions_answered=draft.questions_answered,
            audience_segment=draft.audience_segment,
            recommended_tariff=draft.recommended_tariff,
            readiness_signals=readiness_signals_text,
            final_summary=draft.final_summary,
            crisis_detected=draft.crisis_detected,
        )
        return await repository.create(result_in)
