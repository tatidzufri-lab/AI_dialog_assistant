from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RetreatResult(Base):
    __tablename__ = "retreat_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    questions_answered: Mapped[int] = mapped_column(Integer, nullable=False)
    audience_segment: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    recommended_tariff: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    readiness_signals: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    crisis_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
