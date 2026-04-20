from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import RetreatResult
from schemas import RetreatResultCreate


class RetreatResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, result_in: RetreatResultCreate) -> RetreatResult:
        result = RetreatResult(**result_in.model_dump())
        self._session.add(result)
        await self._session.commit()
        await self._session.refresh(result)
        return result

    async def get_by_id(self, result_id: int) -> RetreatResult | None:
        statement = select(RetreatResult).where(RetreatResult.id == result_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
