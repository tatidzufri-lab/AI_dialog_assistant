from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


AudienceSegment = Literal["perfectionist", "lost_mother", "creative_seeker"]
TariffCode = Literal["path_to_self", "rhythm_of_harmony", "own_peak"]
SessionPhase = Literal[
    "collecting_name", "discovery", "reflection", "recommendation", "completed"
]
AssistantPhase = Literal["discovery", "reflection", "recommendation", "completed"]


TARIFF_LABELS: dict[str, str] = {
    "path_to_self": "Путь к Себе (25 000 ₽)",
    "rhythm_of_harmony": "Ритм Гармонии (50 000 ₽)",
    "own_peak": "Своя Вершина (75 000 ₽)",
}

SEGMENT_LABELS: dict[str, str] = {
    "perfectionist": "Уставшая перфекционистка",
    "lost_mother": "Мама, которая потеряла себя",
    "creative_seeker": "Творческий искатель",
}


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


class RetreatResultCreate(BaseModel):
    participant_name: str = Field(min_length=2, max_length=255)
    telegram_user_id: int
    telegram_chat_id: int
    topic: str = Field(min_length=2, max_length=255)
    total_questions: int = Field(ge=0, le=20)
    questions_answered: int = Field(ge=0, le=20)
    audience_segment: str | None = Field(default=None, max_length=64)
    recommended_tariff: str | None = Field(default=None, max_length=64)
    readiness_signals: str | None = Field(default=None, max_length=2000)
    final_summary: str | None = Field(default=None, max_length=4000)
    crisis_detected: bool = False

    @field_validator("participant_name", "topic", "final_summary", "readiness_signals")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _normalize_text(value)


class RetreatResultRead(RetreatResultCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RetreatSessionDraft(BaseModel):
    participant_name: str | None = None
    phase: SessionPhase = "collecting_name"
    total_questions: int = Field(default=5, ge=3, le=10)
    questions_answered: int = Field(default=0, ge=0, le=20)
    current_question: str | None = None
    last_answer_feedback: str | None = None
    audience_segment: AudienceSegment | None = None
    recommended_tariff: TariffCode | None = None
    readiness_signals: list[str] = Field(default_factory=list)
    final_summary: str | None = None
    crisis_detected: bool = False

    @field_validator(
        "participant_name",
        "current_question",
        "last_answer_feedback",
        "final_summary",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_text(value)

    def remaining_questions(self) -> int:
        return max(self.total_questions - self.questions_answered, 0)


class RetreatAssistantTurn(BaseModel):
    reply: str = Field(min_length=1)
    phase: AssistantPhase
    latest_answer_evaluated: bool = False
    answer_feedback: str | None = None
    next_question: str | None = None
    audience_segment: AudienceSegment | None = None
    recommended_tariff: TariffCode | None = None
    new_readiness_signals: list[str] = Field(default_factory=list)
    final_summary: str | None = None

    @field_validator("answer_feedback", "next_question", "final_summary")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_text(value)
