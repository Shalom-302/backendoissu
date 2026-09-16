from sqlalchemy import Select, and_, asc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.crud.crud_base import CRUDBase
from backend.models import Athlete, Performance, User


class CRUDAthlete(CRUDBase[Athlete]):
    async def get(self, db: AsyncSession, pk: int) -> Athlete | None:
        """Get an athlete by primary key."""
        return await self.select_model(db, pk)

    async def get_by_x_id(self, db: AsyncSession, x_id: str) -> Athlete | None:
        """Get an athlete by public identifier."""
        return await self.select_model_by_column(db, x_id=x_id)

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> Athlete | None:
        """Get the profile owned by a login account."""
        return await self.select_model_by_column(db, user_id=user_id)

    async def get_by_license_number(self, db: AsyncSession, license_number: str) -> Athlete | None:
        """Get an athlete by licence number (unique)."""
        return await self.select_model_by_column(db, license_number=license_number)

    async def get_with_performances(self, db: AsyncSession, pk: int) -> Athlete | None:
        """Get an athlete together with the full performance history."""
        stmt = (
            select(self.model)
            .where(self.model.id == pk)
            .options(selectinload(self.model.performances))
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    def get_list(
        self,
        *,
        q: str | None = None,
        discipline: str | None = None,
        category: str | None = None,
        club_or_establishment: str | None = None,
        is_active: bool | None = None,
    ) -> Select:
        """Build the filtered ADMIN athlete list (doc §15).

        Returns a ``Select`` rather than rows: the caller paginates it.
        """
        stmt = select(self.model).join(User, User.id == self.model.user_id)
        stmt = stmt.order_by(asc(self.model.last_name), asc(self.model.first_name))

        where_list = []
        if q:
            term = f'%{q}%'
            where_list.append(
                or_(
                    self.model.first_name.ilike(term),
                    self.model.last_name.ilike(term),
                    self.model.license_number.ilike(term),
                    self.model.club_or_establishment.ilike(term),
                    User.email.ilike(term),
                )
            )
        if discipline:
            where_list.append(self.model.discipline == discipline)
        if category:
            where_list.append(self.model.category == category)
        if club_or_establishment:
            where_list.append(self.model.club_or_establishment.ilike(f'%{club_or_establishment}%'))
        if is_active is not None:
            where_list.append(User.status == is_active)
        if where_list:
            stmt = stmt.where(and_(*where_list))
        return stmt

    async def create(self, db: AsyncSession, obj: dict) -> Athlete:
        """Insert a profile. The caller owns the transaction."""
        athlete = self.model(**obj)
        db.add(athlete)
        await db.flush()
        await db.refresh(athlete)
        return athlete

    async def update(self, db: AsyncSession, pk: int, obj: dict) -> int:
        """Apply a partial update to a profile."""
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """Delete a profile (the account is removed by the service)."""
        return await self.delete_model(db, pk)

    async def count_active(self, db: AsyncSession) -> int:
        """Athletes whose login account is still enabled."""
        stmt = (
            select(func.count(self.model.id))
            .join(User, User.id == self.model.user_id)
            .where(User.status.is_(True))
        )
        return int((await db.execute(stmt)).scalar_one())

    async def count_performances(self, db: AsyncSession, pk: int) -> int:
        """Number of results recorded for one athlete."""
        stmt = select(func.count(Performance.id)).where(Performance.athlete_id == pk)
        return int((await db.execute(stmt)).scalar_one())

    async def get_disciplines(self, db: AsyncSession) -> list[str]:
        """Distinct disciplines currently represented."""
        stmt = select(self.model.discipline).distinct().order_by(self.model.discipline)
        return [row for row in (await db.execute(stmt)).scalars().all() if row]

    async def get_categories(self, db: AsyncSession) -> list[str]:
        """Distinct categories currently represented."""
        stmt = select(self.model.category).distinct().order_by(self.model.category)
        return [row for row in (await db.execute(stmt)).scalars().all() if row]

    async def get_establishments(self, db: AsyncSession) -> list[str]:
        """Distinct clubs / schools / federations currently represented."""
        stmt = (
            select(self.model.club_or_establishment)
            .distinct()
            .order_by(self.model.club_or_establishment)
        )
        return [row for row in (await db.execute(stmt)).scalars().all() if row]


athlete_dao: CRUDAthlete = CRUDAthlete(Athlete)
