"""Performance business rules (doc §11.3)."""

from fastapi import Request
from sqlalchemy import Select

from backend.app.admin.schema.dashboard import EvolutionPoint
from backend.app.admin.schema.performance import (
    PerformanceCreate,
    PerformanceResponse,
    PerformanceUpdate,
    season_of,
)
from backend.common.exception import errors
from backend.crud.crud_athlete import athlete_dao
from backend.crud.crud_performance import performance_dao
from backend.database.db_postgres import async_db_session
from backend.models import Performance
from backend.utils.translator import Translator


class PerformanceService:
    @staticmethod
    async def create(*, request: Request, obj: PerformanceCreate) -> PerformanceResponse:
        """Record a result against an existing athlete."""
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            if not await athlete_dao.get(db, obj.athlete_id):
                raise errors.NotFoundError(msg=translator.t('athlete.not_found'))
            performance = await performance_dao.create(db, obj.model_dump())
            return PerformanceResponse.model_validate(performance)

    @staticmethod
    def get_select(
        *,
        athlete_id: int | None = None,
        discipline: str | None = None,
        competition_name: str | None = None,
        medal: str | None = None,
        date_from=None,
        date_to=None,
    ) -> Select:
        """Filtered performance list, ready to paginate."""
        return performance_dao.get_list(
            athlete_id=athlete_id,
            discipline=discipline,
            competition_name=competition_name,
            medal=medal,
            date_from=date_from,
            date_to=date_to,
        )

    @staticmethod
    async def get(*, request: Request, pk: int) -> PerformanceResponse:
        """One recorded result."""
        translator = Translator(request.state.locale)
        async with async_db_session() as db:
            performance = await performance_dao.get(db, pk)
            if not performance:
                raise errors.NotFoundError(msg=translator.t('performance.not_found'))
            return PerformanceResponse.model_validate(performance)

    @staticmethod
    async def update(*, request: Request, pk: int, obj: PerformanceUpdate) -> int:
        """Partial update of a recorded result."""
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            if not await performance_dao.get(db, pk):
                raise errors.NotFoundError(msg=translator.t('performance.not_found'))
            data = obj.model_dump(exclude_unset=True, exclude_none=True)
            if not data:
                return 0
            return await performance_dao.update(db, pk, data)

    @staticmethod
    async def delete(*, request: Request, pk: int) -> int:
        """Delete a recorded result."""
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            if not await performance_dao.get(db, pk):
                raise errors.NotFoundError(msg=translator.t('performance.not_found'))
            return await performance_dao.delete(db, pk)

    @staticmethod
    async def get_history(*, request: Request, athlete_id: int) -> list[PerformanceResponse]:
        """Full history of one athlete, most recent first."""
        translator = Translator(request.state.locale)
        async with async_db_session() as db:
            if not await athlete_dao.get(db, athlete_id):
                raise errors.NotFoundError(msg=translator.t('athlete.not_found'))
            rows = await performance_dao.get_by_athlete(db, athlete_id)
            return [PerformanceResponse.model_validate(row) for row in rows]

    @staticmethod
    async def get_my_history(*, request: Request) -> list[PerformanceResponse]:
        """History of the authenticated athlete."""
        translator = Translator(request.state.locale)
        async with async_db_session() as db:
            athlete = await athlete_dao.get_by_user_id(db, request.user.id)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.no_profile'))
            rows = await performance_dao.get_by_athlete(db, athlete.id)
            return [PerformanceResponse.model_validate(row) for row in rows]

    @staticmethod
    def build_evolution(performances: list[Performance]) -> list[EvolutionPoint]:
        """Turn a history into chart points, oldest first.

        Charts read left to right, so the series is reversed here rather than in
        every frontend that consumes it.
        """
        ordered = sorted(performances, key=lambda p: p.competition_date)
        return [
            EvolutionPoint(
                competition_date=p.competition_date,
                competition_name=p.competition_name,
                event=p.event,
                result=p.result,
                unit=p.unit,
                ranking=p.ranking,
                season=season_of(p.competition_date),
            )
            for p in ordered
        ]


performance_service = PerformanceService()
