from datetime import date

from sqlalchemy import Select, and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.crud.crud_base import CRUDBase
from backend.models import Athlete, Performance


class CRUDPerformance(CRUDBase[Performance]):
    async def get(self, db: AsyncSession, pk: int) -> Performance | None:
        """Get a performance by primary key."""
        return await self.select_model(db, pk)

    async def get_by_x_id(self, db: AsyncSession, x_id: str) -> Performance | None:
        """Get a performance by public identifier."""
        return await self.select_model_by_column(db, x_id=x_id)

    async def get_by_athlete(self, db: AsyncSession, athlete_id: int) -> list[Performance]:
        """Full history of one athlete, most recent first."""
        stmt = (
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.competition_date), desc(self.model.id))
        )
        return list((await db.execute(stmt)).scalars().all())

    def get_list(
        self,
        *,
        athlete_id: int | None = None,
        discipline: str | None = None,
        competition_name: str | None = None,
        medal: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Select:
        """Build the filtered ADMIN performance list. The caller paginates it."""
        stmt = select(self.model).order_by(
            desc(self.model.competition_date), desc(self.model.id)
        )

        where_list = []
        if athlete_id:
            where_list.append(self.model.athlete_id == athlete_id)
        if discipline:
            where_list.append(self.model.discipline == discipline)
        if competition_name:
            where_list.append(self.model.competition_name.ilike(f'%{competition_name}%'))
        if medal:
            where_list.append(self.model.medal == medal)
        if date_from:
            where_list.append(self.model.competition_date >= date_from)
        if date_to:
            where_list.append(self.model.competition_date <= date_to)
        if where_list:
            stmt = stmt.where(and_(*where_list))
        return stmt

    async def create(self, db: AsyncSession, obj: dict) -> Performance:
        """Insert a result. The caller owns the transaction."""
        performance = self.model(**obj)
        db.add(performance)
        await db.flush()
        await db.refresh(performance)
        return performance

    async def update(self, db: AsyncSession, pk: int, obj: dict) -> int:
        """Apply a partial update to a result."""
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """Delete a result."""
        return await self.delete_model(db, pk)

    # ------------------------------------------------------------------
    # Aggregations feeding the dashboards (doc §11.4)
    # ------------------------------------------------------------------

    async def count(self, db: AsyncSession, *, athlete_id: int | None = None) -> int:
        """Total number of results, globally or for one athlete."""
        stmt = select(func.count(self.model.id))
        if athlete_id:
            stmt = stmt.where(self.model.athlete_id == athlete_id)
        return int((await db.execute(stmt)).scalar_one())

    async def count_competitions(self, db: AsyncSession, *, athlete_id: int | None = None) -> int:
        """Number of distinct competitions."""
        stmt = select(func.count(func.distinct(self.model.competition_name)))
        if athlete_id:
            stmt = stmt.where(self.model.athlete_id == athlete_id)
        return int((await db.execute(stmt)).scalar_one())

    async def count_medals(self, db: AsyncSession, *, athlete_id: int | None = None) -> dict[str, int]:
        """Tally of distinctions, keyed by medal label."""
        stmt = (
            select(self.model.medal, func.count(self.model.id))
            .where(self.model.medal.isnot(None))
            .group_by(self.model.medal)
        )
        if athlete_id:
            stmt = stmt.where(self.model.athlete_id == athlete_id)
        return {medal: int(total) for medal, total in (await db.execute(stmt)).all()}

    async def best_ranking(self, db: AsyncSession, athlete_id: int) -> int | None:
        """Best (lowest) ranking ever obtained by an athlete."""
        stmt = select(func.min(self.model.ranking)).where(
            self.model.athlete_id == athlete_id, self.model.ranking.isnot(None)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def stats_by_discipline(self, db: AsyncSession) -> list[tuple[str, int, int]]:
        """``(discipline, performances, medals)`` across the whole database."""
        stmt = (
            select(
                self.model.discipline,
                func.count(self.model.id),
                func.count(self.model.medal),
            )
            .group_by(self.model.discipline)
            .order_by(desc(func.count(self.model.id)))
        )
        return [(d, int(p), int(m)) for d, p, m in (await db.execute(stmt)).all()]

    async def athletes_by_discipline(self, db: AsyncSession) -> dict[str, int]:
        """Number of athletes registered per discipline."""
        stmt = select(Athlete.discipline, func.count(Athlete.id)).group_by(Athlete.discipline)
        return {d: int(total) for d, total in (await db.execute(stmt)).all()}

    async def stats_by_month(self, db: AsyncSession) -> list[tuple[str, int, int, int]]:
        """``(YYYY-MM, performances, competitions, medals)``, oldest first."""
        month = func.to_char(self.model.competition_date, 'YYYY-MM')
        stmt = (
            select(
                month,
                func.count(self.model.id),
                func.count(func.distinct(self.model.competition_name)),
                func.count(self.model.medal),
            )
            .group_by(month)
            .order_by(month)
        )
        return [(m, int(p), int(c), int(md)) for m, p, c, md in (await db.execute(stmt)).all()]

    async def count_establishments(self, db: AsyncSession) -> int:
        """Number of distinct clubs / schools engaged in the data."""
        stmt = select(func.count(func.distinct(Athlete.club_or_establishment))).where(
            Athlete.club_or_establishment.isnot(None)
        )
        return int((await db.execute(stmt)).scalar_one())

    async def top_results(self, db: AsyncSession, *, limit: int = 5) -> list[Performance]:
        """Podium-worthy results, best rankings first."""
        stmt = (
            select(self.model)
            .where(self.model.ranking.isnot(None))
            .order_by(self.model.ranking, desc(self.model.competition_date))
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def latest(self, db: AsyncSession, *, limit: int = 10) -> list[Performance]:
        """Most recently held results, all athletes."""
        stmt = (
            select(self.model)
            .order_by(desc(self.model.competition_date), desc(self.model.id))
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())


performance_dao: CRUDPerformance = CRUDPerformance(Performance)
