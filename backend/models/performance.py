from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, get_id, id_key


class Performance(Base):
    """A single result recorded for an athlete at a competition.

    ``result`` is stored as a number (with its ``unit``) rather than free text
    so the dashboards can chart progression without re-parsing strings.
    """

    __tablename__ = 'performance'

    id: Mapped[id_key] = mapped_column(init=False)
    x_id: Mapped[str] = mapped_column(sa.String(32), init=False, unique=True, default=get_id)

    athlete_id: Mapped[int] = mapped_column(
        sa.ForeignKey('athlete.id', ondelete='CASCADE'), index=True, comment='Owning athlete'
    )

    competition_name: Mapped[str] = mapped_column(sa.String(200), index=True)
    competition_date: Mapped[date] = mapped_column(sa.Date, index=True)
    discipline: Mapped[str] = mapped_column(sa.String(100), index=True)
    event: Mapped[str] = mapped_column(sa.String(100), comment='Event / speciality')
    result: Mapped[Decimal] = mapped_column(sa.Numeric(10, 3), comment='Numeric result, see `unit`')
    unit: Mapped[str] = mapped_column(sa.String(20), comment="s, m, cm, pts…")

    location: Mapped[str | None] = mapped_column(sa.String(200), default=None)
    ranking: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='Final ranking (1 = winner)')
    medal: Mapped[str | None] = mapped_column(sa.String(20), index=True, default=None)
    observations: Mapped[str | None] = mapped_column(sa.Text, default=None)

    # selectin: the ADMIN performance list shows who each result belongs to,
    # and lazy='select' would emit a blocking IO call under asyncio.
    athlete: Mapped['Athlete'] = relationship(  # noqa: F821
        init=False, back_populates='performances', lazy='selectin'
    )

    @property
    def athlete_name(self) -> str | None:
        return self.athlete.full_name if self.athlete else None

    @property
    def athlete_license_number(self) -> str | None:
        return self.athlete.license_number if self.athlete else None
