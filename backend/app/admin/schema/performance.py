from datetime import date, datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.enums import Discipline, MedalType
from backend.common.schema import SchemaBase


class PerformanceBase(SchemaBase):
    competition_name: str = Field(min_length=1, max_length=200)
    competition_date: date
    discipline: Discipline | str
    event: str = Field(min_length=1, max_length=100, description='Event / speciality')
    result: Decimal = Field(description='Numeric result, interpreted with `unit`')
    unit: str = Field(min_length=1, max_length=20, description='s, m, cm, pts…')
    location: str | None = None
    ranking: int | None = Field(default=None, ge=1, description='Final ranking (1 = winner)')
    medal: MedalType | str | None = None
    observations: str | None = None


class PerformanceCreate(PerformanceBase):
    athlete_id: int


class PerformanceUpdate(SchemaBase):
    competition_name: str | None = None
    competition_date: date | None = None
    discipline: Discipline | str | None = None
    event: str | None = None
    result: Decimal | None = None
    unit: str | None = None
    location: str | None = None
    ranking: int | None = Field(default=None, ge=1)
    medal: MedalType | str | None = None
    observations: str | None = None


class PerformanceResponse(PerformanceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    x_id: str
    athlete_id: int
    created_time: datetime
    updated_time: datetime | None = None

    @property
    def season(self) -> str:
        return season_of(self.competition_date)


class PerformanceListItem(PerformanceResponse):
    """Row of the ADMIN performance list — carries the athlete identity."""

    athlete_name: str | None = None
    athlete_license_number: str | None = None


def season_of(day: date) -> str:
    """Return the school season a date belongs to, e.g. ``2024-2025``.

    The OISSU season follows the school year: it opens in September and closes
    at the end of August.
    """
    return f'{day.year}-{day.year + 1}' if day.month >= 9 else f'{day.year - 1}-{day.year}'
