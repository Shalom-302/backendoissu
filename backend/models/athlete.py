from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, get_id, id_key


class Athlete(Base):
    """Athlete profile — the OISSU CONNECT "fiche athlète".

    Exactly one profile per ``User`` of role USER (an ADMIN has none). The
    account and the profile are always created together, in a single
    transaction (see ``AthleteService.create``).
    """

    __tablename__ = 'athlete'

    id: Mapped[id_key] = mapped_column(init=False)
    x_id: Mapped[str] = mapped_column(sa.String(32), init=False, unique=True, default=get_id)

    # One-to-one with the login account. CASCADE: deleting the account removes
    # the profile, so no orphan athlete can survive its user.
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('user.id', ondelete='CASCADE'), unique=True, index=True, comment='Owning user account'
    )

    license_number: Mapped[str] = mapped_column(
        sa.String(64), unique=True, index=True, comment='OISSU licence / identifier'
    )
    first_name: Mapped[str] = mapped_column(sa.String(100), index=True)
    last_name: Mapped[str] = mapped_column(sa.String(100), index=True)
    discipline: Mapped[str] = mapped_column(sa.String(100), index=True, comment='Main discipline')

    speciality: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='Event / speciality')
    category: Mapped[str | None] = mapped_column(sa.String(50), index=True, default=None, comment='Age category')
    club_or_establishment: Mapped[str | None] = mapped_column(
        sa.String(200), index=True, default=None, comment='Club, school or federation'
    )
    education_level: Mapped[str | None] = mapped_column(sa.String(50), default=None)
    nationality: Mapped[str | None] = mapped_column(sa.String(100), default=None)
    gender: Mapped[str | None] = mapped_column(sa.String(20), default=None)
    date_of_birth: Mapped[date | None] = mapped_column(sa.Date, default=None)
    photo_url: Mapped[str | None] = mapped_column(sa.String(500), default=None)

    # Unidirectional on purpose: User stays untouched by the OISSU domain.
    user: Mapped['User'] = relationship(init=False, lazy='selectin')  # noqa: F821
    performances: Mapped[list['Performance']] = relationship(  # noqa: F821
        init=False,
        back_populates='athlete',
        cascade='all, delete-orphan',
        lazy='noload',
        order_by='desc(Performance.competition_date)',
    )

    # --- Account state, surfaced on the profile -----------------------------
    # The athlete has no `is_active` column of its own: the single source of
    # truth is the login account (``User.status``), so enabling/disabling an
    # athlete can never drift from their ability to log in.

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def is_active(self) -> bool:
        return bool(self.user.status) if self.user else False

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()
